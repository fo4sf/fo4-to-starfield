# Commonwealth diagnostic movement correction

Agent: Codex. The owner resumed testing with Claude retaining controller priority. This isolated runner correction preserves the original af27ce9 campaign and captures.

The terrain runner applied the measured merge offset to judged points but sent its final unscored diagnostic in raw local coordinates. The corrected call adds the measured X/Y offset and reuses the computed world drop height, including the existing drop-above-spawn option. Heading and pitch remain90/5. It changes no planned points, source assets, collision or acceptance rules.

Three synthetic tests parse the actual qstep PowerShell command and execute only that command against a JSON-producing Teleport stub. They exercise a nonzero XYZ merge offset, a zero-offset control and a computed drop-above-spawn height. The two nonzero cases fail on the original runner. No qstep body or input helper executes during testing.

```powershell
python -B -m unittest discover -s tests -p test_qstep_post_offset.py
```

Independent review and a freshly pinned runner/campaign are required before live use. Do not edit the original campaign hashes or repeat its completed smoke/baseline merely to replace history. Run the remaining informational phase separately, inspect all actual XYZ/captures, and retain expected object-height failures. No sampled landing proves walking, connected interiors or full-map acceptance.
