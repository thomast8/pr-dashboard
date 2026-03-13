/** Version badge that shows release notes on click. */

import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { api, type ReleaseInfo } from '../api/client';
import styles from './VersionBadge.module.css';

export function VersionBadge() {
  const { data } = useQuery({
    queryKey: ['version'],
    queryFn: api.getVersion,
    staleTime: 1000 * 60 * 60, // 1 hour
  });

  const [showModal, setShowModal] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);

  const { data: releases } = useQuery({
    queryKey: ['releases'],
    queryFn: api.getReleases,
    staleTime: 1000 * 60 * 60,
    enabled: showModal,
  });

  // Reset index when modal opens
  useEffect(() => {
    if (showModal) setCurrentIndex(0);
  }, [showModal]);

  const canGoNewer = currentIndex > 0;
  const canGoOlder = !!releases && currentIndex < releases.length - 1;

  const goNewer = useCallback(() => {
    if (canGoNewer) setCurrentIndex((i) => i - 1);
  }, [canGoNewer]);

  const goOlder = useCallback(() => {
    if (canGoOlder) setCurrentIndex((i) => i + 1);
  }, [canGoOlder]);

  // Keyboard navigation
  useEffect(() => {
    if (!showModal) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setShowModal(false);
      if (e.key === 'ArrowLeft') goNewer();
      if (e.key === 'ArrowRight') goOlder();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [showModal, goNewer, goOlder]);

  if (!data) return null;

  // Use release data if available, fall back to version endpoint data
  const current: ReleaseInfo | null = releases?.[currentIndex] ?? null;
  const displayName = current?.release_name ?? data.release_name ?? `v${data.version}`;
  const displayDate = current?.published_at ?? data.published_at;
  const displayNotes = current?.release_notes ?? data.release_notes;
  const displayUrl = current?.release_url ?? data.release_url;
  const totalReleases = releases?.length ?? 0;

  return (
    <>
      <button
        className={styles.badge}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowModal(true); }}
        title="View release notes"
      >
        v{data.version}
      </button>

      {showModal && createPortal(
        <div className={styles.overlay} onClick={() => setShowModal(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div className={styles.headerLeft}>
                <h2 className={styles.modalTitle}>{displayName}</h2>
                {displayDate && (
                  <span className={styles.modalDate}>
                    {new Date(displayDate).toLocaleDateString(undefined, {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </span>
                )}
              </div>
              {totalReleases > 1 && (
                <div className={styles.navControls}>
                  <button
                    className={styles.navBtn}
                    onClick={goNewer}
                    disabled={!canGoNewer}
                    title="Newer release"
                  >
                    &#8592;
                  </button>
                  <span className={styles.navCounter}>
                    {currentIndex + 1} of {totalReleases}
                  </span>
                  <button
                    className={styles.navBtn}
                    onClick={goOlder}
                    disabled={!canGoOlder}
                    title="Older release"
                  >
                    &#8594;
                  </button>
                </div>
              )}
              <button className={styles.closeBtn} onClick={() => setShowModal(false)}>
                &times;
              </button>
            </div>

            <div className={styles.modalBody}>
              {displayNotes ? (
                <ReactMarkdown>{displayNotes}</ReactMarkdown>
              ) : (
                <p className={styles.noNotes}>No release notes available.</p>
              )}
            </div>

            {displayUrl && (
              <div className={styles.modalFooter}>
                <a
                  href={displayUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.releaseLink}
                >
                  View on GitHub
                </a>
              </div>
            )}
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
