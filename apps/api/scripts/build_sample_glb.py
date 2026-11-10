"""Write two homemade glTF binaries: a door with two meshes, and a cabinet."""

import json
import struct
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "web" / "public" / "models"


def _box(x0, y0, z0, x1, y1, z1):
    corners = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    ]
    positions = []
    indices = []
    for a, b, c, d in faces:
        start = len(positions) // 3
        for index in (a, b, c, d):
            positions.extend(corners[index])
        indices.extend((start, start + 1, start + 2, start, start + 2, start + 3))
    return positions, indices


def _glb(meshes: list[tuple[str, list[float], list[int]]]) -> bytes:
    blob = bytearray()
    accessors = []
    buffer_views = []
    primitives = []
    nodes = []
    for name, positions, indices in meshes:
        pos = struct.pack(f"<{len(positions)}f", *positions)
        idx = struct.pack(f"<{len(indices)}H", *indices)
        pos_pad = b"\x00" * ((4 - len(pos) % 4) % 4)
        pos_offset = len(blob)
        blob += pos + pos_pad
        idx_offset = len(blob)
        blob += idx + b"\x00" * ((4 - len(idx) % 4) % 4)
        view_pos = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": pos_offset, "byteLength": len(pos), "target": 34962})
        view_idx = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": idx_offset, "byteLength": len(idx), "target": 34963})
        xs = positions[0::3]
        ys = positions[1::3]
        zs = positions[2::3]
        acc_pos = len(accessors)
        accessors.append(
            {
                "bufferView": view_pos,
                "componentType": 5126,
                "count": len(positions) // 3,
                "type": "VEC3",
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
            }
        )
        acc_idx = len(accessors)
        accessors.append({"bufferView": view_idx, "componentType": 5123, "count": len(indices), "type": "SCALAR"})
        mesh_index = len(primitives)
        primitives.append({"name": name, "primitives": [{"attributes": {"POSITION": acc_pos}, "indices": acc_idx}]})
        nodes.append({"name": name, "mesh": mesh_index})
    gltf = {
        "asset": {"version": "2.0", "generator": "fitout-example"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": primitives,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(blob)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    bin_chunk = bytes(blob) + b"\x00" * ((4 - len(blob) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(bin_chunk)
    out = struct.pack("<III", 0x46546C67, 2, total)
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(bin_chunk), 0x004E4942) + bin_chunk
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frame, frame_idx = _box(-0.48, 0, 0, 0.48, 2.1, 0.08)
    leaf, leaf_idx = _box(-0.40, 0.05, 0.04, 0.40, 2.02, 0.08)
    door = _glb([("门框", frame, frame_idx), ("门扇", leaf, leaf_idx)])
    cabinet, cabinet_idx = _box(-0.9, 0, -0.3, 0.9, 2.4, 0.3)
    box = _glb([("柜体", cabinet, cabinet_idx)])
    (OUT / "door-sample.glb").write_bytes(door)
    (OUT / "cabinet-sample.glb").write_bytes(box)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
