/** Version badge that shows release notes on click. */

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { api } from '../api/client';
import styles from './VersionBadge.module.css';

export function VersionBadge() {
  const { data } = useQuery({
    queryKey: ['version'],
    queryFn: api.getVersion,
    staleTime: 1000 * 60 * 60, // 1 hour
  });

  const [showModal, setShowModal] = useState(false);

  // Close on Escape
  useEffect(() => {
    if (!showModal) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setShowModal(false);
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [showModal]);

  if (!data) return null;

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
              <div>
                <h2 className={styles.modalTitle}>
                  {data.release_name || `v${data.version}`}
                </h2>
                {data.published_at && (
                  <span className={styles.modalDate}>
                    {new Date(data.published_at).toLocaleDateString(undefined, {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </span>
                )}
              </div>
              <button className={styles.closeBtn} onClick={() => setShowModal(false)}>
                &times;
              </button>
            </div>

            <div className={styles.modalBody}>
              {data.release_notes ? (
                <ReactMarkdown>{data.release_notes}</ReactMarkdown>
              ) : (
                <p className={styles.noNotes}>No release notes available.</p>
              )}
            </div>

            {data.release_url && (
              <div className={styles.modalFooter}>
                <a
                  href={data.release_url}
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
