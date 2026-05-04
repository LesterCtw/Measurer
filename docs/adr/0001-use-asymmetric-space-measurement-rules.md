# 使用非對稱 Space 量測規則

Horizontal Space 與 Vertical Space 刻意使用不同量測規則。Horizontal Space 使用相鄰 Metal Islands 的 Refined Boundary 水平範圍間距，原因是 LK shrinkage 可能讓 metal islands 上下位移，直接做 horizontal scan 不一定符合工程判讀。Vertical Space 會在 shared x-range 內做垂直 scans，並回報最小 boundary-to-boundary gap，因為 bounding-box vertical gap 可能漏掉上下 metal boundaries 之間真正最近的垂直距離。
