# Use Asymmetric Space Measurement Rules

Horizontal Space and Vertical Space intentionally use different measurement rules. Horizontal Space uses the gap between adjacent Metal Islands' Refined Boundary horizontal extents because LK shrinkage can move metal islands vertically, making a horizontal scan less representative of engineering judgment. Vertical Space uses vertical scans over the shared x-range and reports the minimum boundary-to-boundary gap because bounding-box vertical gap can miss the closest true vertical spacing between upper and lower metal boundaries.
