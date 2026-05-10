#version 330 core
// Fullscreen quad vertex shader.
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec2 aUV;

out vec2 vUV;

void main() {
    gl_Position = vec4(aPos, 1.0);
    vUV = vec2(aUV.x, 1.0 - aUV.y); // Flip V so OpenCV image appears upright.
}
