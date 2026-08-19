import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq

t = pq.read_table(r"D:\ic\tmp\ds\data.parquet")
print("columns:", t.column_names)
print("rows:", t.num_rows)

ep_idx = t.column("episode_index").to_numpy()
print("episodes:", np.unique(ep_idx)[:10], "... total", len(np.unique(ep_idx)))

mask = pc.equal(t.column("episode_index"), 0)
ep0 = t.filter(mask)
print("episode 0 frames:", ep0.num_rows)

a = np.stack(ep0.column("action").to_pylist())
s = np.stack(ep0.column("observation.state").to_pylist())
np.set_printoptions(precision=4, suppress=True, linewidth=220)
print("action shape:", a.shape)
print("action[0]    :", a[0])
print("action[n/3]  :", a[len(a) // 3])
print("action[-1]   :", a[-1])
print("action min   :", a.min(axis=0))
print("action max   :", a.max(axis=0))
print()
print("state[0]     :", s[0])
print()
print("ch14 every30 :", a[::30, 14])
print("ch15 every30 :", a[::30, 15])

tasks = pq.read_table(r"D:\ic\tmp\ds\tasks.parquet")
print()
print("tasks columns:", tasks.column_names)
print("tasks:", tasks.to_pylist()[:5])
