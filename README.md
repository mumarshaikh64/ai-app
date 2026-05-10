# Real-Time AR Face + Body Filter (OpenGL + MediaPipe)

## Features implemented
- OpenCV webcam capture and BGR→RGB upload into `GL_TEXTURE_2D`.
- Fullscreen camera quad rendering.
- MediaPipe FaceMesh (468 landmarks), Pose (33 keypoints), and Selfie Segmentation.
- Landmark conversion to NDC and upload via uniform arrays.
- Face effects: 3D overlay, face warp, skin smoothing.
- Body effects: glowing skeleton, virtual clothing warp, mask-based background replacement.
- Motion trail ghosting with 5 textures.
- Final composite pass with hue/saturation/brightness/contrast/vignette grading.

## Setup
1. Create environment and install deps:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Ensure webcam access is available.
3. Run:
   ```bash
   python main.py
   ```

## Rendering loop order
1. `glClear`
2. Draw camera background quad
3. Run AI inference (FaceMesh + Pose + Segmentation)
4. Upload landmarks/keypoints/mask to GPU
5. Draw face overlays (warp, skin smooth, 3D overlay)
6. Draw body overlays (skeleton, clothing)
7. Draw particles
8. Composite pass (scene + segmentation + background + trail + color grade)
9. `glfwSwapBuffers`

## Notes on performance
- Uses VAO/VBO with dynamic updates only where required.
- Reuses textures/FBOs every frame (no per-frame reallocations).
- Keeps draw call count low with fullscreen passes.
- On a mid-range GPU, expected to be around or above 30 FPS depending on camera resolution and MediaPipe latency.
