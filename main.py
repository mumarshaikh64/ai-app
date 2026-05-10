#!/usr/bin/env python3
"""
Real-time AR Face + Body Filter demo pipeline.

Stack:
- Python + OpenCV webcam capture
- MediaPipe FaceMesh / Pose / SelfieSegmentation for AI inference
- GLFW + PyOpenGL for rendering
- NumPy for CPU-side math

This implementation focuses on a complete, understandable render graph with explicit
OpenGL calls and comments, matching the requested feature set.
"""

from __future__ import annotations
import ctypes
import math
import time
from dataclasses import dataclass
from collections import deque

import cv2
import glfw
import mediapipe as mp
import numpy as np
from OpenGL.GL import *


WIN_W, WIN_H = 1280, 720
MAX_FACE_LANDMARKS = 468
MAX_BODY_KEYPOINTS = 33
MOTION_TRAIL_COUNT = 5

# Minimal line topology for MediaPipe pose skeleton (33 keypoints)
POSE_EDGES = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
    (24, 26), (26, 28), (27, 31), (28, 32)
]


@dataclass
class Shader:
    program: int

    def use(self):
        glUseProgram(self.program)  # Bind shader program for subsequent draw calls.



def compile_shader(src: str, shader_type: int) -> int:
    shader = glCreateShader(shader_type)  # Create empty shader object (vertex or fragment).
    glShaderSource(shader, src)  # Attach GLSL source to shader object.
    glCompileShader(shader)  # Compile GLSL source into GPU executable.
    if glGetShaderiv(shader, GL_COMPILE_STATUS) != GL_TRUE:
        raise RuntimeError(glGetShaderInfoLog(shader).decode())
    return shader



def load_shader_program(vert_path: str, frag_path: str) -> Shader:
    with open(vert_path, "r", encoding="utf-8") as f:
        vs = f.read()
    with open(frag_path, "r", encoding="utf-8") as f:
        fs = f.read()

    v = compile_shader(vs, GL_VERTEX_SHADER)
    f = compile_shader(fs, GL_FRAGMENT_SHADER)

    prog = glCreateProgram()  # Create program pipeline object that links stages.
    glAttachShader(prog, v)  # Attach compiled vertex shader to program.
    glAttachShader(prog, f)  # Attach compiled fragment shader to program.
    glLinkProgram(prog)  # Link all attached stages into a runnable GPU program.
    if glGetProgramiv(prog, GL_LINK_STATUS) != GL_TRUE:
        raise RuntimeError(glGetProgramInfoLog(prog).decode())

    glDeleteShader(v)  # Shader objects can be deleted after successful link.
    glDeleteShader(f)
    return Shader(prog)



def make_texture(width: int, height: int, internal=GL_RGBA8, fmt=GL_RGBA, typ=GL_UNSIGNED_BYTE) -> int:
    tex = glGenTextures(1)  # Allocate one OpenGL texture object handle.
    glBindTexture(GL_TEXTURE_2D, tex)  # Bind texture so subsequent setup applies to it.
    glTexImage2D(GL_TEXTURE_2D, 0, internal, width, height, 0, fmt, typ, None)  # Allocate GPU storage.
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)  # Linear minification sampling.
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)  # Linear magnification sampling.
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)  # Clamp U to avoid seams.
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)  # Clamp V to avoid seams.
    glBindTexture(GL_TEXTURE_2D, 0)  # Unbind for cleanliness.
    return tex



def create_fullscreen_quad() -> tuple[int, int]:
    vertices = np.array([
        # x, y, z, u, v
        -1.0, -1.0, 0.0, 0.0, 0.0,
         1.0, -1.0, 0.0, 1.0, 0.0,
         1.0,  1.0, 0.0, 1.0, 1.0,
        -1.0,  1.0, 0.0, 0.0, 1.0,
    ], dtype=np.float32)
    indices = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)

    vao = glGenVertexArrays(1)  # Create VAO describing vertex format bindings.
    vbo = glGenBuffers(1)  # Create VBO for vertex data.
    ebo = glGenBuffers(1)  # Create EBO for indexed drawing.

    glBindVertexArray(vao)  # Bind VAO to record attribute state.
    glBindBuffer(GL_ARRAY_BUFFER, vbo)  # Bind VBO as array buffer target.
    glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)  # Upload quad vertices.
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)  # Bind index buffer to VAO.
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)  # Upload indices.

    stride = 5 * ctypes.sizeof(ctypes.c_float)
    glEnableVertexAttribArray(0)  # Enable attribute location 0 (position).
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))  # Position layout.
    glEnableVertexAttribArray(1)  # Enable attribute location 1 (uv).
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))  # UV layout.

    glBindVertexArray(0)  # Unbind VAO.
    return vao, ebo



def create_skeleton_vao() -> tuple[int, int]:
    vao = glGenVertexArrays(1)
    vbo = glGenBuffers(1)

    glBindVertexArray(vao)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, len(POSE_EDGES) * 2 * 2 * 4, None, GL_DYNAMIC_DRAW)  # Dynamic line vertices.
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * 4, ctypes.c_void_p(0))
    glBindVertexArray(0)
    return vao, vbo



def ndc_from_normalized(x: float, y: float) -> tuple[float, float]:
    return x * 2.0 - 1.0, 1.0 - y * 2.0



def upload_pose_lines(vbo: int, keypoints: np.ndarray):
    line_points = []
    for a, b in POSE_EDGES:
        line_points.extend([keypoints[a, 0], keypoints[a, 1], keypoints[b, 0], keypoints[b, 1]])
    line_points = np.array(line_points, dtype=np.float32)

    glBindBuffer(GL_ARRAY_BUFFER, vbo)  # Bind skeleton VBO to update line geometry.
    glBufferSubData(GL_ARRAY_BUFFER, 0, line_points.nbytes, line_points)  # Replace line vertices with latest pose.



def simple_mvp(scale=1.0, tx=0.0, ty=0.0, tz=0.0) -> np.ndarray:
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = scale
    m[1, 1] = scale
    m[2, 2] = scale
    m[0, 3] = tx
    m[1, 3] = ty
    m[2, 3] = tz
    return m



def main():
    # -------- GLFW / OpenGL init --------
    if not glfw.init():
        raise RuntimeError("Failed to init GLFW")
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)  # Request OpenGL 3.x context major version.
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)  # Request OpenGL 3.3 core profile.
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)  # Core profile for modern OpenGL APIs.

    window = glfw.create_window(WIN_W, WIN_H, "Real-Time AR Face + Body Filters", None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("Failed to create window")
    glfw.make_context_current(window)  # Make GL context current on this thread.
    glfw.swap_interval(1)  # Enable VSync to reduce tearing and stabilize frame pacing.

    glViewport(0, 0, WIN_W, WIN_H)  # Define drawable viewport dimensions.
    glEnable(GL_BLEND)  # Enable blending for alpha compositing overlays.

    # -------- Camera capture --------
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIN_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam")

    # -------- AI models (MediaPipe) --------
    mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False, max_num_faces=1, refine_landmarks=True,
        min_detection_confidence=0.5, min_tracking_confidence=0.5
    )
    mp_pose = mp.solutions.pose.Pose(
        static_image_mode=False, model_complexity=1,
        min_detection_confidence=0.5, min_tracking_confidence=0.5
    )
    mp_seg = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)

    # -------- GPU resources --------
    quad_vao, quad_ebo = create_fullscreen_quad()
    skel_vao, skel_vbo = create_skeleton_vao()

    camera_tex = make_texture(WIN_W, WIN_H, GL_RGB8, GL_RGB, GL_UNSIGNED_BYTE)
    mask_tex = make_texture(WIN_W, WIN_H, GL_R8, GL_RED, GL_UNSIGNED_BYTE)
    bg_tex = make_texture(WIN_W, WIN_H, GL_RGB8, GL_RGB, GL_UNSIGNED_BYTE)

    trail_tex = [make_texture(WIN_W, WIN_H, GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE) for _ in range(MOTION_TRAIL_COUNT)]
    trail_queue = deque(maxlen=MOTION_TRAIL_COUNT)

    # Main scene FBO
    scene_fbo = glGenFramebuffers(1)
    scene_color = make_texture(WIN_W, WIN_H, GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE)
    glBindFramebuffer(GL_FRAMEBUFFER, scene_fbo)  # Bind FBO for offscreen render target setup.
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, scene_color, 0)  # Attach color tex.
    if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
        raise RuntimeError("Scene FBO incomplete")
    glBindFramebuffer(GL_FRAMEBUFFER, 0)

    # -------- Shaders --------
    sh_camera = load_shader_program("shaders/camera_quad.vert", "shaders/camera_quad.frag")
    sh_overlay = load_shader_program("shaders/face_overlay.vert", "shaders/face_overlay.frag")
    sh_warp = load_shader_program("shaders/camera_quad.vert", "shaders/face_warp.frag")
    sh_skin = load_shader_program("shaders/camera_quad.vert", "shaders/skin_smooth.frag")
    sh_skel = load_shader_program("shaders/skeleton.vert", "shaders/skeleton.frag")
    sh_cloth = load_shader_program("shaders/clothing_warp.vert", "shaders/clothing_warp.frag")
    sh_particle = load_shader_program("shaders/particle.vert", "shaders/particle.frag")
    sh_comp = load_shader_program("shaders/camera_quad.vert", "shaders/composite.frag")

    # Fake background texture (gradient)
    bg_img = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)
    for y in range(WIN_H):
        c = int(255 * y / WIN_H)
        bg_img[y, :, :] = (c // 2, c, 255 - c)
    glBindTexture(GL_TEXTURE_2D, bg_tex)
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, WIN_W, WIN_H, GL_RGB, GL_UNSIGNED_BYTE, bg_img)

    # Placeholder data containers
    face_landmarks_ndc = np.zeros((MAX_FACE_LANDMARKS, 2), dtype=np.float32)
    body_keypoints_ndc = np.zeros((MAX_BODY_KEYPOINTS, 2), dtype=np.float32)
    body_visible = np.zeros((MAX_BODY_KEYPOINTS,), dtype=np.float32)

    # Very basic cube data used as "glasses/hat" proxy mesh
    cube = np.array([
        -0.1, -0.05, 0.0, 0.0, 0.0,
         0.1, -0.05, 0.0, 1.0, 0.0,
         0.1,  0.05, 0.0, 1.0, 1.0,
        -0.1,  0.05, 0.0, 0.0, 1.0,
    ], dtype=np.float32)
    cube_idx = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)

    cube_vao = glGenVertexArrays(1)
    cube_vbo = glGenBuffers(1)
    cube_ebo = glGenBuffers(1)
    glBindVertexArray(cube_vao)
    glBindBuffer(GL_ARRAY_BUFFER, cube_vbo)
    glBufferData(GL_ARRAY_BUFFER, cube.nbytes, cube, GL_STATIC_DRAW)
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, cube_ebo)
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, cube_idx.nbytes, cube_idx, GL_STATIC_DRAW)
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 5 * 4, ctypes.c_void_p(0))
    glEnableVertexAttribArray(1)
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 5 * 4, ctypes.c_void_p(12))
    glBindVertexArray(0)

    # Particle VAO uses face landmarks as GL_POINTS
    particle_vao = glGenVertexArrays(1)
    particle_vbo = glGenBuffers(1)
    glBindVertexArray(particle_vao)
    glBindBuffer(GL_ARRAY_BUFFER, particle_vbo)
    glBufferData(GL_ARRAY_BUFFER, MAX_FACE_LANDMARKS * 2 * 4, None, GL_DYNAMIC_DRAW)
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * 4, ctypes.c_void_p(0))
    glBindVertexArray(0)

    t0 = time.time()
    fps_counter = 0

    while not glfw.window_should_close(window):
        ok, frame_bgr = cap.read()
        if not ok:
            break

        frame_bgr = cv2.flip(frame_bgr, 1)
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # ---- AI inference ----
        face_result = mp_face_mesh.process(frame_rgb)
        pose_result = mp_pose.process(frame_rgb)
        seg_result = mp_seg.process(frame_rgb)

        if face_result.multi_face_landmarks:
            lms = face_result.multi_face_landmarks[0].landmark
            for i in range(min(len(lms), MAX_FACE_LANDMARKS)):
                x, y = lms[i].x, lms[i].y
                face_landmarks_ndc[i] = ndc_from_normalized(x, y)

        if pose_result.pose_landmarks:
            for i, lm in enumerate(pose_result.pose_landmarks.landmark[:MAX_BODY_KEYPOINTS]):
                body_keypoints_ndc[i] = ndc_from_normalized(lm.x, lm.y)
                body_visible[i] = 1.0 if lm.visibility > 0.3 else 0.0

        if seg_result.segmentation_mask is not None:
            mask = (seg_result.segmentation_mask > 0.5).astype(np.uint8) * 255
            glBindTexture(GL_TEXTURE_2D, mask_tex)
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, mask.shape[1], mask.shape[0], GL_RED, GL_UNSIGNED_BYTE, mask)

        # Upload camera RGB frame
        glBindTexture(GL_TEXTURE_2D, camera_tex)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, frame_rgb.shape[1], frame_rgb.shape[0], GL_RGB, GL_UNSIGNED_BYTE, frame_rgb)

        # Update dynamic VBOs
        upload_pose_lines(skel_vbo, body_keypoints_ndc)
        glBindBuffer(GL_ARRAY_BUFFER, particle_vbo)
        glBufferSubData(GL_ARRAY_BUFFER, 0, face_landmarks_ndc.nbytes, face_landmarks_ndc)

        # -------- Render graph --------
        glBindFramebuffer(GL_FRAMEBUFFER, scene_fbo)  # Render to offscreen scene texture for post-processing/composite.
        glClearColor(0.05, 0.05, 0.06, 1.0)  # Set background clear color.
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)  # Clear color/depth before drawing new frame.

        # 1) Camera background
        sh_camera.use()
        glActiveTexture(GL_TEXTURE0)  # Activate texture unit 0 for camera sampler.
        glBindTexture(GL_TEXTURE_2D, camera_tex)  # Bind camera texture object.
        glUniform1i(glGetUniformLocation(sh_camera.program, "uCameraTex"), 0)  # camera_quad.frag: sampler2D uCameraTex
        glBindVertexArray(quad_vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)  # Draw fullscreen quad.

        # 2) Face warp pass as simple overlay sample
        sh_warp.use()
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, camera_tex)
        glUniform1i(glGetUniformLocation(sh_warp.program, "uInputTex"), 0)  # face_warp.frag input texture
        glUniform2fv(glGetUniformLocation(sh_warp.program, "uFaceLandmarks"), MAX_FACE_LANDMARKS, face_landmarks_ndc.flatten())  # Landmark uniform array.
        glUniform1i(glGetUniformLocation(sh_warp.program, "uLandmarkCount"), MAX_FACE_LANDMARKS)
        glUniform1f(glGetUniformLocation(sh_warp.program, "uEyeScale"), 0.12)
        glUniform1f(glGetUniformLocation(sh_warp.program, "uFaceSlim"), 0.08)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

        # 3) Skin smoothing overlay
        sh_skin.use()
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, camera_tex)
        glUniform1i(glGetUniformLocation(sh_skin.program, "uInputTex"), 0)  # skin_smooth.frag input texture
        glUniform2f(glGetUniformLocation(sh_skin.program, "uTexelSize"), 1.0 / WIN_W, 1.0 / WIN_H)
        glUniform1f(glGetUniformLocation(sh_skin.program, "uSmoothStrength"), 0.55)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

        # 4a) 3D face mesh proxy overlay with MVP from pseudo solvePnP
        sh_overlay.use()
        glBindVertexArray(cube_vao)
        mvp = simple_mvp(scale=1.2, tx=0.0, ty=0.2, tz=0.0)
        glUniformMatrix4fv(glGetUniformLocation(sh_overlay.program, "uMVP"), 1, GL_TRUE, mvp)  # face_overlay.vert: mat4 MVP
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, bg_tex)
        glUniform1i(glGetUniformLocation(sh_overlay.program, "uOverlayTex"), 0)
        glUniform1f(glGetUniformLocation(sh_overlay.program, "uAlpha"), 0.7)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

        # 4b) Glowing skeleton
        sh_skel.use()
        glBindVertexArray(skel_vao)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)  # Additive blending for glow lines.
        glUniform3f(glGetUniformLocation(sh_skel.program, "uGlowColor"), 0.1, 0.8, 1.0)
        glUniform1f(glGetUniformLocation(sh_skel.program, "uGlowIntensity"), 1.6)
        glLineWidth(4.0)
        glDrawArrays(GL_LINES, 0, len(POSE_EDGES) * 2)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)  # Restore standard alpha blending.

        # 4c) Clothing quad mapped by shoulder/hip points
        sh_cloth.use()
        glBindVertexArray(quad_vao)
        # shoulders (11,12), hips (23,24): left-top, right-top, left-bottom, right-bottom
        cps = np.array([
            body_keypoints_ndc[11], body_keypoints_ndc[12],
            body_keypoints_ndc[23], body_keypoints_ndc[24],
        ], dtype=np.float32).flatten()
        glUniform2fv(glGetUniformLocation(sh_cloth.program, "uControlPts"), 4, cps)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, bg_tex)
        glUniform1i(glGetUniformLocation(sh_cloth.program, "uClothTex"), 0)
        glUniform1f(glGetUniformLocation(sh_cloth.program, "uAlpha"), 0.55)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

        # 4d) Face particles
        sh_particle.use()
        glBindVertexArray(particle_vao)
        glEnable(GL_PROGRAM_POINT_SIZE)
        t = time.time() - t0
        glUniform1f(glGetUniformLocation(sh_particle.program, "uTime"), t)
        glUniform1f(glGetUniformLocation(sh_particle.program, "uPointSize"), 4.0)
        glDrawArrays(GL_POINTS, 0, MAX_FACE_LANDMARKS)

        # Save scene texture into trail ring
        trail_queue.appendleft(scene_color)

        # Final pass to screen: background replacement + motion trail + color grade
        glBindFramebuffer(GL_FRAMEBUFFER, 0)  # Bind default framebuffer (screen).
        glClear(GL_COLOR_BUFFER_BIT)
        sh_comp.use()
        glBindVertexArray(quad_vao)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, scene_color)
        glUniform1i(glGetUniformLocation(sh_comp.program, "uSceneTex"), 0)

        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, camera_tex)
        glUniform1i(glGetUniformLocation(sh_comp.program, "uCameraTex"), 1)

        glActiveTexture(GL_TEXTURE2)
        glBindTexture(GL_TEXTURE_2D, bg_tex)
        glUniform1i(glGetUniformLocation(sh_comp.program, "uBgTex"), 2)

        glActiveTexture(GL_TEXTURE3)
        glBindTexture(GL_TEXTURE_2D, mask_tex)
        glUniform1i(glGetUniformLocation(sh_comp.program, "uMaskTex"), 3)

        # Bind motion trail textures (up to 5)
        for i in range(MOTION_TRAIL_COUNT):
            glActiveTexture(GL_TEXTURE4 + i)
            tex = trail_queue[i] if i < len(trail_queue) else scene_color
            glBindTexture(GL_TEXTURE_2D, tex)
            glUniform1i(glGetUniformLocation(sh_comp.program, f"uTrailTex[{i}]"), 4 + i)

        glUniform1f(glGetUniformLocation(sh_comp.program, "uHueShift"), 0.05)
        glUniform1f(glGetUniformLocation(sh_comp.program, "uSaturation"), 1.12)
        glUniform1f(glGetUniformLocation(sh_comp.program, "uBrightness"), 0.02)
        glUniform1f(glGetUniformLocation(sh_comp.program, "uContrast"), 1.05)
        glUniform1f(glGetUniformLocation(sh_comp.program, "uVignette"), 0.35)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

        glfw.swap_buffers(window)
        glfw.poll_events()

        fps_counter += 1
        if fps_counter % 120 == 0:
            dt = time.time() - t0
            print(f"FPS: {fps_counter / max(dt, 1e-5):.2f}")

    cap.release()
    glfw.terminate()


if __name__ == "__main__":
    main()
