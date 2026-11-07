"""Build small neutral PBR maps. Hue comes from the scheme color in the material."""

from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parents[1] / "public" / "textures"
SIZE = 512


def value_noise(height: int, width: int, cell: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    grid_h = height // cell + 2
    grid_w = width // cell + 2
    grid = rng.random((grid_h, grid_w))
    ys = np.linspace(0, grid_h - 2, height)
    xs = np.linspace(0, grid_w - 2, width)
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    g00 = grid[y0[:, None], x0[None, :]]
    g10 = grid[y0[:, None] + 1, x0[None, :]]
    g01 = grid[y0[:, None], x0[None, :] + 1]
    g11 = grid[y0[:, None] + 1, x0[None, :] + 1]
    return g00 * (1 - fy) * (1 - fx) + g10 * fy * (1 - fx) + g01 * (1 - fy) * fx + g11 * fy * fx


def fbm(height: int, width: int, seed: int) -> np.ndarray:
    total = np.zeros((height, width))
    weight = 0.0
    for octave, cell in enumerate((128, 64, 32, 16)):
        amp = 0.5**octave
        total += amp * value_noise(height, width, cell, seed + octave * 17)
        weight += amp
    return total / weight


def normals_from_height(height: np.ndarray, strength: float) -> np.ndarray:
    grad_y, grad_x = np.gradient(height.astype(np.float32))
    normal_x = -grad_x * strength
    normal_y = -grad_y * strength
    normal_z = np.ones_like(height, dtype=np.float32)
    length = np.sqrt(normal_x**2 + normal_y**2 + normal_z**2)
    rgb = np.stack(((normal_x / length + 1) / 2, (normal_y / length + 1) / 2, (normal_z / length + 1) / 2), axis=-1)
    return np.clip(rgb * 255, 0, 255).astype(np.uint8)


def save_pack(name: str, albedo: np.ndarray, roughness: np.ndarray, height: np.ndarray, normal_strength: float) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rgb = np.clip(albedo * 255, 0, 255).astype(np.uint8)
    if rgb.ndim == 2:
        rgb = np.repeat(rgb[:, :, None], 3, axis=2)
    Image.fromarray(rgb, "RGB").save(OUT / f"{name}-albedo.png", optimize=True)
    Image.fromarray(np.clip(roughness * 255, 0, 255).astype(np.uint8), "L").save(OUT / f"{name}-roughness.png", optimize=True)
    Image.fromarray(normals_from_height(height, normal_strength), "RGB").save(OUT / f"{name}-normal.png", optimize=True)


def paint() -> None:
    fine = value_noise(SIZE, SIZE, 8, 11)
    albedo = 0.97 + (fine - 0.5) * 0.015
    roughness = 0.97 + (fine - 0.5) * 0.02
    save_pack("paint", albedo, roughness, fine * 0.04, 2.5)


def wood() -> None:
    albedo = np.zeros((SIZE, SIZE))
    height = np.zeros((SIZE, SIZE))
    roughness = np.zeros((SIZE, SIZE))
    plank = 56
    for index, y0 in enumerate(range(0, SIZE, plank)):
        y1 = min(SIZE, y0 + plank)
        rows = y1 - y0
        band = fbm(rows, SIZE, 20 + index)
        phase = band[min(3, rows - 1)]
        streaks = 0.5 + 0.5 * np.sin(np.linspace(0, 36 + index * 3, SIZE) + phase * 4)
        pores = 0.5 + 0.5 * np.sin(np.linspace(0, 90, SIZE) * (1.3 + index * 0.07))
        tone = 0.78 + (0 if index % 2 == 0 else 0.16)
        grain = np.clip(0.55 + 0.45 * streaks * (0.65 + 0.35 * pores), 0.35, 1)
        albedo[y0:y1] = tone * grain * (0.86 + 0.14 * band)
        height[y0:y1] = (streaks - 0.4) * 0.45 + band * 0.2
        roughness[y0:y1] = 0.48 + (1 - streaks) * 0.28
        seam = slice(max(y0, y1 - 5), y1)
        albedo[seam] *= 0.22
        height[seam] -= 0.8
        roughness[seam] = 0.96
    save_pack("wood", albedo, roughness, height, 11.0)


def parquet() -> None:
    albedo = np.full((SIZE, SIZE), 0.7)
    height = np.zeros((SIZE, SIZE))
    roughness = np.full((SIZE, SIZE), 0.72)
    for row in range(0, SIZE, 40):
        for col in range(0, SIZE, 40):
            flip = ((row // 40) + (col // 40)) % 2 == 0
            bw, bh = (120, 26) if flip else (26, 120)
            x1, y1 = min(SIZE, col + bw), min(SIZE, row + bh)
            tone = 0.58 if (row + col) % 80 == 0 else 0.96
            albedo[row:y1, col:x1] = tone
            roughness[row:y1, col:x1] = 0.5 if tone > 0.8 else 0.7
            height[row:y1, col:x1] = 0.45 if tone > 0.8 else 0.15
            albedo[row:y1, max(col, x1 - 3) : x1] *= 0.25
            albedo[max(row, y1 - 3) : y1, col:x1] *= 0.25
            height[row:y1, max(col, x1 - 3) : x1] = 0
            height[max(row, y1 - 3) : y1, col:x1] = 0
    save_pack("parquet", albedo, roughness, height, 8.0)


def tile(name: str, grout: int, grout_albedo: float) -> None:
    albedo = np.full((SIZE, SIZE), grout_albedo)
    roughness = np.full((SIZE, SIZE), 1.0)
    height = np.zeros((SIZE, SIZE))
    field = fbm(SIZE, SIZE, 8)
    inner = field[grout:-grout, grout:-grout]
    albedo[grout:-grout, grout:-grout] = 0.98 + (inner - 0.5) * 0.03
    roughness[grout:-grout, grout:-grout] = 0.16
    height[grout:-grout, grout:-grout] = 0.7
    save_pack(name, albedo, roughness, height, 14.0)


def stone() -> None:
    grain = fbm(SIZE, SIZE, 5)
    veins = np.zeros((SIZE, SIZE))
    xs = np.linspace(0, 1, SIZE)
    ys = np.linspace(0, 1, SIZE)
    grid_y, grid_x = np.meshgrid(ys, xs, indexing="ij")
    for index in range(8):
        shift = 0.17 * index
        band = np.sin((grid_x * (4 + index) + grid_y * (0.8 + index * 0.35) + shift) * np.pi)
        veins += np.clip(band - 0.55, 0, 1)
    veins = np.clip(veins, 0, 1)
    albedo = 0.97 + (grain - 0.5) * 0.04 - veins * 0.85
    roughness = 0.32 + veins * 0.4
    save_pack("stone", np.clip(albedo, 0.08, 1), roughness, grain * 0.15 - veins * 0.8, 6.0)


def leather() -> None:
    pebbles = value_noise(SIZE, SIZE, 6, 42)
    albedo = 0.9 + (pebbles - 0.5) * 0.08
    roughness = 0.84 + (1 - pebbles) * 0.08
    save_pack("leather", albedo, roughness, pebbles, 5.5)


if __name__ == "__main__":
    paint()
    wood()
    parquet()
    tile("tile", 22, 0.16)
    tile("grout", 40, 0.05)
    stone()
    leather()
    print(f"wrote textures to {OUT}")
