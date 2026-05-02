# Use Simple MVS State and Export Rules

Measurer's MVS will keep image state, measurement status, and export behavior intentionally simple: only images with at least one successful final measurement are `Measured`, ROI changes delete old measurement results instead of keeping stale results, and Export only writes `Measured` images. Pending and Failed images stay visible in the GUI but do not produce Result Images, Debug Images, or Excel rows, while diagnostic quality indicators such as fallback ratio stay in the Trace Sheet for produced final measurements.

This favors a predictable guided workflow over complex recovery, stale-result handling, or partial export management. The trade-off is that failed image reasons are not preserved in exported Excel and skipped files are reported through GUI summaries rather than detailed exported logs, but the exported artifacts remain clean and easier for engineers to interpret.
