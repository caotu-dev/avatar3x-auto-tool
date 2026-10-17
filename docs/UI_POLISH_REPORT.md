# UI responsiveness — 2026-10-17

The Activity card now shows the current preparation, running, pause, reconnect or error status. The initial status also explains what is required to enable Start. This previously existed only in an unbound variable.

Worker progress bursts now produce one presentation update per poll, and log lines are inserted in a batch. Preparation, completion and error notifications flush earlier progress and logs before displaying. The log view keeps at most 1,500 lines, preserves the reader's scroll position, and does not rebuild the text widget. A poll handles at most 200 queued events and catches up after 15 ms when more remain. Ordinary polling runs every 75 ms; the timer changes only once per second.

Identical progress rows and unchanged labels no longer redraw. Layout requests share one pending idle job. Banner resize events are debounced by 30 ms, decoded header variants use a bounded two-entry cache, and transferring pixels to Tk uses PPM directly instead of compressing a new PNG on every resize. Settings fields only change their enabled state when the running state changes; Ctrl+Enter saves the modal draft.

The three-column proportions, full-height progress, 2×2 controls below tickets, supplied clock icon, all three modes, ordering, settings validation and Save/Cancel semantics remain intact. Programmatic geometry checks with all thirteen fish, complete ticket expiry text and long bait labels found no page scrollbar at:

| Window | Content required | Available |
| --- | ---: | ---: |
| 1536×960 | 656 px | 730 px |
| 1440×900 | 617 px | 670 px |
| 1280×800 | 540 px | 574 px |
| 1024×720 | 516 px | 522 px |

Verification: eight dedicated responsiveness checks cover a 120-event burst becoming one table/log update, lifecycle notification ordering, unchanged values, log bounds, one layout job, bounded header caching, settings locks and the smallest supported dashboard. Existing UI tests also pass. These changes reduce presentation work; they do not alter game action timing or recognition thresholds.
