using System.Buffers.Binary;
using System.IO.Compression;
using System.Text;

/// <summary>
/// Reads Starfield NVNM navmesh triangles from a core ESM (FO4TerrainCore.esm) and snaps actor Z onto floor navmesh.
/// </summary>
public static class NavmeshSnap
{
    public const float DefaultMaxSnapDz = 2.5f;
    public const float HoldFloorMaxToleranceM = 0.2f;

    public sealed record NavMeshData(
        uint FormId,
        float MinX,
        float MaxX,
        float MinY,
        float MaxY,
        float[] Verts,
        short[] Tris);

    public static List<NavMeshData> LoadWorldNavmeshes(string esmPath)
    {
        var result = new List<NavMeshData>();
        if (!File.Exists(esmPath)) return result;

        var data = File.ReadAllBytes(esmPath);
        if (data.Length < 24) return result;
        int tes4Size = BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan(4, 4));
        int pos = 24 + tes4Size;

        void ScanGroup(int start, int end)
        {
            int q = start;
            while (q + 24 <= end)
            {
                var sig = Encoding.ASCII.GetString(data, q, 4);
                int gsz = BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan(q + 4, 4));
                if (sig == "GRUP")
                {
                    if (gsz < 24 || q + gsz > end) break;
                    ScanGroup(q + 24, q + gsz);
                    q += gsz;
                }
                else
                {
                    if (gsz < 0 || q + 24 + gsz > end) break;
                    uint flags = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(q + 8, 4));
                    uint fid = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(q + 12, 4));
                    if (sig == "NAVM")
                    {
                        var body = ExtractBody(data, q + 24, gsz, (flags & 0x40000u) != 0);
                        if (TryParseNvnm(fid, body, out var nav)) result.Add(nav);
                    }
                    q += 24 + gsz;
                }
            }
        }

        while (pos + 24 <= data.Length)
        {
            var sig = Encoding.ASCII.GetString(data, pos, 4);
            int sz = BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan(pos + 4, 4));
            if (sig == "GRUP")
            {
                if (sz < 24 || pos + sz > data.Length) break;
                var lbl = Encoding.ASCII.GetString(data, pos + 8, 4);
                int gtype = BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan(pos + 12, 4));
                if (gtype == 0 && lbl == "WRLD")
                    ScanGroup(pos + 24, pos + sz);
                pos += sz;
            }
            else
            {
                if (sz < 0 || pos + 24 + sz > data.Length) break;
                pos += 24 + sz;
            }
        }
        return result;
    }

    static ReadOnlySpan<byte> ExtractBody(byte[] data, int offset, int size, bool compressed)
    {
        if (!compressed) return data.AsSpan(offset, size);
        if (size < 6) return ReadOnlySpan<byte>.Empty;
        int uncompSize = BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan(offset, 4));
        if (uncompSize <= 0 || uncompSize > 32 * 1024 * 1024) return ReadOnlySpan<byte>.Empty;
        var outBuf = new byte[uncompSize];
        using var ms = new MemoryStream(data, offset + 4, size - 4);
        using var zs = new ZLibStream(ms, CompressionMode.Decompress);
        int readTotal = 0;
        while (readTotal < uncompSize)
        {
            int n = zs.Read(outBuf, readTotal, uncompSize - readTotal);
            if (n <= 0) break;
            readTotal += n;
        }
        return readTotal == uncompSize ? outBuf : ReadOnlySpan<byte>.Empty;
    }

    static bool TryParseNvnm(uint formId, ReadOnlySpan<byte> body, out NavMeshData nav)
    {
        nav = default!;
        int p = 0;
        while (p + 6 <= body.Length)
        {
            var tag = Encoding.ASCII.GetString(body.Slice(p, 4));
            int slen = BinaryPrimitives.ReadUInt16LittleEndian(body.Slice(p + 4, 2));
            p += 6;
            if (p + slen > body.Length) return false;
            if (tag == "NVNM")
            {
                var d = body.Slice(p, slen);
                if (d.Length < 24) return false;
                uint ver = BinaryPrimitives.ReadUInt32LittleEndian(d);
                int q = 16; // version(4)+magic(4)+world(4)+grid/cell(4)
                int nv = BinaryPrimitives.ReadInt32LittleEndian(d.Slice(q, 4));
                q += 4;
                int vStride = ver >= 17 ? 16 : 12;
                if (nv <= 0 || q + nv * vStride + 4 > d.Length) return false;
                var verts = new float[nv * 3];
                float minX = float.MaxValue, maxX = float.MinValue, minY = float.MaxValue, maxY = float.MinValue;
                for (int i = 0; i < nv; i++)
                {
                    float vx = BinaryPrimitives.ReadSingleLittleEndian(d.Slice(q, 4));
                    float vy = BinaryPrimitives.ReadSingleLittleEndian(d.Slice(q + 4, 4));
                    float vz = BinaryPrimitives.ReadSingleLittleEndian(d.Slice(q + 8, 4));
                    verts[i * 3] = vx;
                    verts[i * 3 + 1] = vy;
                    verts[i * 3 + 2] = vz;
                    if (vx < minX) minX = vx;
                    if (vx > maxX) maxX = vx;
                    if (vy < minY) minY = vy;
                    if (vy > maxY) maxY = vy;
                    q += vStride;
                }
                int nt = BinaryPrimitives.ReadInt32LittleEndian(d.Slice(q, 4));
                q += 4;
                if (nt <= 0 || q + nt * 21 > d.Length) return false;
                var tris = new short[nt * 3];
                for (int i = 0; i < nt; i++)
                {
                    short v0 = BinaryPrimitives.ReadInt16LittleEndian(d.Slice(q, 2));
                    short v1 = BinaryPrimitives.ReadInt16LittleEndian(d.Slice(q + 2, 2));
                    short v2 = BinaryPrimitives.ReadInt16LittleEndian(d.Slice(q + 4, 2));
                    if (v0 < 0 || v0 >= nv || v1 < 0 || v1 >= nv || v2 < 0 || v2 >= nv) return false;
                    tris[i * 3] = v0;
                    tris[i * 3 + 1] = v1;
                    tris[i * 3 + 2] = v2;
                    q += 21;
                }
                nav = new NavMeshData(formId, minX, maxX, minY, maxY, verts, tris);
                return true;
            }
            p += slen;
        }
        return false;
    }

    public static bool TryFindFloorZ(
        IReadOnlyList<NavMeshData> navs,
        float x,
        float y,
        float refZ,
        out float floorZ,
        float maxDz = DefaultMaxSnapDz)
    {
        floorZ = refZ;
        float bestDiff = maxDz + 1e-4f;
        bool found = false;
        foreach (var nav in navs)
        {
            if (x < nav.MinX - 0.1f || x > nav.MaxX + 0.1f || y < nav.MinY - 0.1f || y > nav.MaxY + 0.1f)
                continue;
            int nt = nav.Tris.Length / 3;
            var v = nav.Verts;
            var t = nav.Tris;
            for (int ti = 0; ti < nt; ti++)
            {
                int i0 = t[ti * 3] * 3, i1 = t[ti * 3 + 1] * 3, i2 = t[ti * 3 + 2] * 3;
                float x0 = v[i0], y0 = v[i0 + 1], z0 = v[i0 + 2];
                float x1 = v[i1], y1 = v[i1 + 1], z1 = v[i1 + 2];
                float x2 = v[i2], y2 = v[i2 + 1], z2 = v[i2 + 2];
                float denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2);
                if (MathF.Abs(denom) < 1e-7f) continue;
                float a = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / denom;
                float b = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / denom;
                float c = 1f - a - b;
                if (a >= -1e-4f && b >= -1e-4f && c >= -1e-4f)
                {
                    float tz = a * z0 + b * z1 + c * z2;
                    float diff = MathF.Abs(tz - refZ);
                    if (diff < bestDiff)
                    {
                        bestDiff = diff;
                        floorZ = tz;
                        found = true;
                    }
                }
            }
        }
        return found;
    }
}
