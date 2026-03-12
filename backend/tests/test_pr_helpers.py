"""Tests for PR helper functions: rebase detection, bot detection, commenters, reviewers."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from src.api.pulls import (
    _commenters_without_review,
    _compute_all_reviewers,
    _is_bot_login,
    _rebased_since_approval,
)


@dataclass
class FakeReview:
    reviewer: str
    state: str
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    commit_id: str | None = None


@dataclass
class FakePR:
    head_sha: str | None = "abc123"
    reviews: list = field(default_factory=list)
    github_requested_reviewers: list = field(default_factory=list)
    commenters: list | None = None


# ── _rebased_since_approval ──────────────────────────


class TestRebasedSinceApproval:
    def test_no_reviews(self):
        """No reviews = not rebased."""
        pr = FakePR(reviews=[])
        assert _rebased_since_approval(pr) is False

    def test_no_approvals(self):
        """Reviews exist but none are approvals."""
        pr = FakePR(reviews=[FakeReview("alice", "COMMENTED", commit_id="abc123")])
        assert _rebased_since_approval(pr) is False

    def test_approval_matches_head(self):
        """Approval commit matches head SHA = not rebased."""
        pr = FakePR(
            head_sha="abc123",
            reviews=[FakeReview("alice", "APPROVED", commit_id="abc123")],
        )
        assert _rebased_since_approval(pr) is False

    def test_approval_differs_from_head(self):
        """Approval commit differs from head = rebased."""
        pr = FakePR(
            head_sha="new_sha",
            reviews=[FakeReview("alice", "APPROVED", commit_id="old_sha")],
        )
        assert _rebased_since_approval(pr) is True

    def test_no_head_sha(self):
        """No head SHA on PR = not rebased."""
        pr = FakePR(head_sha=None, reviews=[FakeReview("alice", "APPROVED", commit_id="abc")])
        assert _rebased_since_approval(pr) is False

    def test_approval_without_commit_id(self):
        """Approval has no commit_id = not rebased."""
        pr = FakePR(
            head_sha="abc123",
            reviews=[FakeReview("alice", "APPROVED", commit_id=None)],
        )
        assert _rebased_since_approval(pr) is False

    def test_multiple_reviewers_latest_approval(self):
        """Uses the latest approval across all reviewers."""
        now = datetime.now(UTC)
        pr = FakePR(
            head_sha="new_sha",
            reviews=[
                FakeReview(
                    "alice", "APPROVED", submitted_at=now - timedelta(hours=5), commit_id="old_sha"
                ),
                FakeReview(
                    "bob", "APPROVED", submitted_at=now - timedelta(hours=1), commit_id="old_sha"
                ),
                FakeReview(
                    "alice", "COMMENTED", submitted_at=now
                ),  # latest from alice, but not approval
            ],
        )
        # bob's approval (most recent approval) has old_sha != new_sha
        assert _rebased_since_approval(pr) is True

    def test_reviewer_overrides_earlier_approval(self):
        """A reviewer's later non-approval state overrides their earlier approval."""
        now = datetime.now(UTC)
        pr = FakePR(
            head_sha="abc123",
            reviews=[
                FakeReview(
                    "alice", "APPROVED", submitted_at=now - timedelta(hours=2), commit_id="old_sha"
                ),
                FakeReview("alice", "CHANGES_REQUESTED", submitted_at=now, commit_id="abc123"),
            ],
        )
        # alice's latest state is CHANGES_REQUESTED, so no approvals remain
        assert _rebased_since_approval(pr) is False


# ── _is_bot_login ────────────────────────────────────


class TestIsBotLogin:
    @pytest.mark.parametrize(
        "login, expected",
        [
            ("dependabot[bot]", True),
            ("github-actions[bot]", True),
            ("copilot", True),
            ("Copilot", True),  # case-insensitive
            ("alice", False),
            ("bob-reviewer", False),
            ("botuser", False),  # "bot" substring without [bot] suffix is not a bot
        ],
    )
    def test_bot_detection(self, login, expected):
        assert _is_bot_login(login) == expected


# ── _commenters_without_review ───────────────────────


class TestCommentersWithoutReview:
    def test_no_commenters(self):
        pr = FakePR(commenters=None)
        assert _commenters_without_review(pr) == []

    def test_empty_commenters(self):
        pr = FakePR(commenters=[])
        assert _commenters_without_review(pr) == []

    def test_commenter_is_also_reviewer(self):
        """Commenter who submitted a formal review is excluded."""
        pr = FakePR(
            commenters=["alice"],
            reviews=[FakeReview("alice", "APPROVED")],
        )
        assert _commenters_without_review(pr) == []

    def test_commenter_is_requested_reviewer(self):
        """Commenter who is a requested reviewer is excluded."""
        pr = FakePR(
            commenters=["bob"],
            github_requested_reviewers=[{"login": "bob"}],
        )
        assert _commenters_without_review(pr) == []

    def test_bot_commenter_excluded(self):
        """Bot commenters are filtered out."""
        pr = FakePR(commenters=["dependabot[bot]", "copilot"])
        assert _commenters_without_review(pr) == []

    def test_genuine_commenter_included(self):
        """A commenter who hasn't reviewed and isn't requested is included."""
        pr = FakePR(
            commenters=["charlie", "alice"],
            reviews=[FakeReview("alice", "COMMENTED")],
        )
        assert _commenters_without_review(pr) == ["charlie"]

    def test_sorted_output(self):
        """Output is sorted alphabetically."""
        pr = FakePR(commenters=["zoe", "alice", "bob"])
        result = _commenters_without_review(pr)
        assert result == ["alice", "bob", "zoe"]


# ── _compute_all_reviewers ───────────────────────────


class TestComputeAllReviewers:
    def test_requested_only(self):
        """Requested reviewers with no reviews show as pending."""
        pr = FakePR(
            reviews=[],
            github_requested_reviewers=[
                {"login": "alice", "avatar_url": "https://example.com/alice.png"},
            ],
        )
        result = _compute_all_reviewers(pr)
        assert len(result) == 1
        assert result[0]["login"] == "alice"
        assert result[0]["review_state"] == "pending"
        assert result[0]["avatar_url"] == "https://example.com/alice.png"

    def test_reviewed_only(self):
        """Reviewer who submitted a review but isn't in the requested list."""
        pr = FakePR(
            reviews=[FakeReview("bob", "APPROVED")],
            github_requested_reviewers=[],
        )
        result = _compute_all_reviewers(pr)
        assert len(result) == 1
        assert result[0]["login"] == "bob"
        assert result[0]["review_state"] == "approved"
        assert result[0]["avatar_url"] is None

    def test_mix_requested_and_reviewed(self):
        """Requested reviewer who also submitted a review gets their review state."""
        pr = FakePR(
            reviews=[FakeReview("alice", "CHANGES_REQUESTED")],
            github_requested_reviewers=[
                {"login": "alice", "avatar_url": "https://example.com/alice.png"},
                {"login": "bob", "avatar_url": None},
            ],
        )
        result = _compute_all_reviewers(pr)
        by_login = {r["login"]: r for r in result}
        assert by_login["alice"]["review_state"] == "changes_requested"
        assert by_login["bob"]["review_state"] == "pending"

    def test_sort_order(self):
        """Sort: changes_requested < pending < commented < approved."""
        now = datetime.now(UTC)
        pr = FakePR(
            reviews=[
                FakeReview("approver", "APPROVED", submitted_at=now),
                FakeReview("changer", "CHANGES_REQUESTED", submitted_at=now),
                FakeReview("commenter", "COMMENTED", submitted_at=now),
            ],
            github_requested_reviewers=[{"login": "pending_person"}],
        )
        result = _compute_all_reviewers(pr)
        logins = [r["login"] for r in result]
        assert logins == ["changer", "pending_person", "commenter", "approver"]

    def test_alphabetical_within_group(self):
        """Within the same state group, reviewers are sorted alphabetically."""
        now = datetime.now(UTC)
        pr = FakePR(
            reviews=[
                FakeReview("zoe", "APPROVED", submitted_at=now),
                FakeReview("alice", "APPROVED", submitted_at=now),
            ],
        )
        result = _compute_all_reviewers(pr)
        logins = [r["login"] for r in result]
        assert logins == ["alice", "zoe"]

    def test_empty(self):
        """No reviewers and no requested reviewers."""
        pr = FakePR(reviews=[], github_requested_reviewers=[])
        assert _compute_all_reviewers(pr) == []
