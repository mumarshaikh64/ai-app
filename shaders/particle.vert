#version 330 core
layout(location = 0) in vec2 aPos;
out float vLife;

uniform float uTime;
uniform float uPointSize;

void main() {
    gl_Position = vec4(aPos, 0.0, 1.0);
    gl_PointSize = uPointSize;
    vLife = fract(uTime * 0.2 + (aPos.x + aPos.y) * 0.5);
}
