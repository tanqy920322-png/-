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
    grain = fbm(SIZE, SIZE, 3)
    fine = value_noise(SIZE, SIZE, 4, 11)
    albedo = 0.93 + (grain - 0.5) * 0.05 + (fine - 0.5) * 0.02
    roughness = 0.9 + (fine - 0.5) * 0.06
    save_pack("paint", albedo, roughness, fine * 0.15, 4.0)


def wood() -> None:
    albedo = np.zeros((SIZE, SIZE))
    height = np.zeros((SIZE, SIZE))
    roughness = np.zeros((SIZE, SIZE))
    plank = 64
    for index, y0 in enumerate(range(0, SIZE, plank)):
        y1 = min(SIZE, y0 + plank)
        band = fbm(y1 - y0, SIZE, 20 + index)
        streaks = 0.5 + 0.5 * np.sin(np.linspace(0, 28 + index, SIZE) + band[0] * 2)
        tone = 0.9 + (band.mean() - 0.5) * 0.08
        albedo[y0:y1] = tone * (0.92 + 0.08 * streaks)
        albedo[y0:y1] *= 0.94 + 0.06 * band
        height[y0:y1] = band * 0.25 + streaks * 0.15
        roughness[y0:y1] = 0.62 + (1 - streaks) * 0.12
        albedo[max(y0, y1 - 3) : y1] *= 0.55
        height[max(y0, y1 - 3) : y1] -= 0.45
        roughness[max(y0, y1 - 3) : y1] = 0.88
    save_pack("wood", albedo, roughness, height, 6.0)


def parquet() -> None:
    albedo = np.full((SIZE, SIZE), 0.86)
    height = np.zeros((SIZE, SIZE))
    roughness = np.full((SIZE, SIZE), 0.66)
    block_w, block_h = 28, 112
    for row in range(0, SIZE, 36):
        for col in range(0, SIZE, 36):
            horizontal = ((row // 36) + (col // 36)) % 2 == 0
            bw, bh = (block_h, block_w) if horizontal else (block_w, block_h)
            x1, y1 = min(SIZE, col + bw), min(SIZE, row + bh)
            tone = 0.82 + ((row + col) % 5) * 0.025
            albedo[row:y1, col:x1] = tone
            roughness[row:y1, col:x1] = 0.6
            height[row:y1, col:x1] = 0.2
            albedo[row:y1, x1 - 2 : x1] *= 0.62
            albedo[y1 - 2 : y1, col:x1] *= 0.62
            height[row:y1, x1 - 2 : x1] = 0
            height[y1 - 2 : y1, col:x1] = 0
    save_pack("parquet", albedo, roughness, height, 5.0)


def tile(name: str, grout: int, grout_albedo: float) -> None:
    albedo = np.full((SIZE, SIZE), grout_albedo)
    roughness = np.full((SIZE, SIZE), 0.95)
    height = np.zeros((SIZE, SIZE))
    field = fbm(SIZE, SIZE, 8)
    albedo[grout:-grout, grout:-grout] = 0.96 + (field[grout:-grout, grout:-grout] - 0.5) * 0.04
    roughness[grout:-grout, grout:-grout] = 0.42
    height[grout:-grout, grout:-grout] = 0.35 + field[grout:-grout, grout:-grout] * 0.05
    save_pack(name, albedo, roughness, height, 7.0)


def stone() -> None:
    grain = fbm(SIZE, SIZE, 5)
    veins = np.zeros((SIZE, SIZE))
    xs = np.linspace(0, 1, SIZE)
    ys = np.linspace(0, 1, SIZE)
    grid_y, grid_x = np.meshgrid(ys, xs, indexing="ij")
    for index in range(6):
        shift = 0.15 * index
        band = np.sin((grid_x * (3 + index) + grid_y * (1.2 + index * 0.3) + shift) * np.pi)
        veins += np.clip(band, 0.72, 1) - 0.72
    albedo = 0.94 + (grain - 0.5) * 0.05 - veins * 0.55
    roughness = 0.58 + veins * 0.15
    save_pack("stone", albedo, roughness, grain * 0.2 - veins, 4.5)


def leather() -> None:
    pebbles = value_noise(SIZE, SIZE, 6, 42)
    albedo = 0.9 + (pebbles - 0.5) * 0.08
    roughness = 0.84 + (1 - pebbles) * 0.08
    save_pack("leather", albedo, roughness, pebbles, 5.5)


if __name__ == "__main__":
    paint()
    wood()
    parquet()
    tile("tile", 14, 0.38)
    tile("grout", 28, 0.12)
    stone()
    leather()
    print(f"wrote textures to {OUT}")
