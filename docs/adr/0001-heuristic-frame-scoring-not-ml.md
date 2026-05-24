# Heuristic frame scoring, not ML, for v1

The original brief talked about finding "interesting frames with any sort of wildlife", so the natural read is to reach for a wildlife detector (MegaDetector, YOLO, CLIP zero-shot). We deliberately didn't.

v1 scores Frames with a composite heuristic computed in OpenCV at 3fps sampling: sharpness (Laplacian variance) + edge density (Canny mean) + colour variance (HSV S-channel stddev). No PyTorch, no model weights, no GPU. The hypothesis is that for scuba footage specifically, "empty blue water" is reliably low on edges and colour variance, so the discriminating signal between "frame contains something" and "frame is open water" falls out of cheap pixel math without needing a learned detector.

## Considered options

- **MegaDetector v6**: purpose-built animal detector. Rejected for v1 because of the 500MB model, PyTorch dependency, and the fact it doesn't recognise non-animal Subjects the user wants later (wrecks, statues, coral).
- **YOLOv8 / COCO classes**: general detector. Rejected for limited animal coverage, no marine-specific classes (no fish class), and the same PyTorch dependency.
- **CLIP zero-shot**: flexible via text prompts, naturally extensible to non-animal categories. Rejected for v1 but kept as the leading candidate for v2 when the first non-Wildlife category is added.

## Consequences

- "Subject detection" in v1 is an inference, not a confirmation. A frame with high Score might just be a sharp, colourful patch of coral with no animal in it, and that's fine; the user wants to keep frames like that anyway.
- The `FrameAnalyser` Protocol (see ADR-0002) makes adding a real ML-based analyser, or any alternative heuristic, a sibling addition rather than a pipeline rewrite.
- Re-tuning the score weights (`--force` reprocess + new weights) is cheap because per-frame component scores are stored in SQLite. See ADR-0002.
