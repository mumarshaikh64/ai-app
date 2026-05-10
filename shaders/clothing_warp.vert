#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec2 aUV;
out vec2 vUV;

uniform vec2 uControlPts[4];

void main() {
    // Bilinear warp from torso corners:
    // p00 left-shoulder, p10 right-shoulder, p01 left-hip, p11 right-hip
    vec2 p00 = uControlPts[0];
    vec2 p10 = uControlPts[1];
    vec2 p01 = uControlPts[2];
    vec2 p11 = uControlPts[3];

    float u = aUV.x;
    float v = aUV.y;
    vec2 p = mix(mix(p00, p10, u), mix(p01, p11, u), v);

    gl_Position = vec4(p, 0.0, 1.0);
    vUV = aUV;
}
