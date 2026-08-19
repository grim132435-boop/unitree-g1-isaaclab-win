"""공식 데이터셋에서 그리퍼 개폐 이벤트 구간만 뽑는다 (시뮬 불필요)."""
import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq

PATH = r"D:\ic\tmp\ds\data.parquet"
EP = 0

t = pq.read_table(PATH)
ep = t.filter(pc.equal(t.column("episode_index"), EP))
a = np.stack(ep.column("action").to_pylist()).astype(np.float32)
print(f"episode {EP}: {len(a)} frames")

# [14]=right gripper, [15]=left gripper  (0=closed, 5.4=open)
for ch, name in ((14, "right"), (15, "left")):
    g = a[:, ch]
    closed = g < 2.7  # 임계 중간값
    # 전이 지점
    trans = np.where(np.diff(closed.astype(int)) != 0)[0]
    print(f"\n--- {name} gripper (ch{ch}) ---")
    print(f"  closed frames: {closed.sum()} / {len(g)}")
    segs = []
    start = 0
    cur = closed[0]
    for i in trans:
        segs.append((start, i, "CLOSED" if cur else "open"))
        start = i + 1
        cur = closed[i + 1]
    segs.append((start, len(g) - 1, "CLOSED" if cur else "open"))
    for s, e, st in segs:
        if e - s < 5:
            continue
        print(f"  {st:6s} frames {s:5d}-{e:5d}  ({(e-s)/30.0:5.2f}s)")
