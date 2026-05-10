#version 330 core
layout(location = 0) in vec2 aPos;
out float vPulse;
uniform float uTime;

void main() {
    gl_Position = vec4(aPos, 0.0, 1.0);
    vPulse = 0.5 + 0.5 * sin(uTime * 4.0 + aPos.x * 10.0);
}
