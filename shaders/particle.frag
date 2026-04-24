#version 330 core
in float vLife;
out vec4 FragColor;

void main() {
    vec2 p = gl_PointCoord * 2.0 - 1.0;
    float d = dot(p, p);
    if (d > 1.0) discard;
    float a = (1.0 - d) * (1.0 - vLife);
    FragColor = vec4(1.0, 0.7, 0.2, a);
}
