from PIL import Image

im = Image.open("run_notes/complete_victory_live/hq_t3_exchange_move_miss.png").convert("RGB")
pix = im.load()
mask = set()
for y in range(250, 1150):
    for x in range(300, 1700):
        r, g, b = pix[x, y]
        if r > 180 and g > 160 and b < 90 and abs(r - g) < 100:
            mask.add((x, y))

seen = set()
components = []
for point in list(mask):
    if point in seen:
        continue
    queue = [point]
    seen.add(point)
    xs = []
    ys = []
    idx = 0
    while idx < len(queue):
        x, y = queue[idx]
        idx += 1
        xs.append(x)
        ys.append(y)
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nxt in mask and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    if len(xs) > 20:
        components.append((
            len(xs),
            min(xs),
            min(ys),
            max(xs),
            max(ys),
            sum(xs) // len(xs),
            sum(ys) // len(ys),
        ))

for component in sorted(components, reverse=True)[:40]:
    print(component)

print("--- green ---")
mask = set()
for y in range(250, 1150):
    for x in range(300, 1700):
        r, g, b = pix[x, y]
        if g > 140 and g > r + 25 and g > b + 15:
            mask.add((x, y))

seen = set()
components = []
for point in list(mask):
    if point in seen:
        continue
    queue = [point]
    seen.add(point)
    xs = []
    ys = []
    idx = 0
    while idx < len(queue):
        x, y = queue[idx]
        idx += 1
        xs.append(x)
        ys.append(y)
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nxt in mask and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    if len(xs) > 50:
        components.append((
            len(xs),
            min(xs),
            min(ys),
            max(xs),
            max(ys),
            sum(xs) // len(xs),
            sum(ys) // len(ys),
        ))

for component in sorted(components, reverse=True)[:60]:
    print(component)
