#version 330 core
in float vPulse;
out vec4 FragColor;

uniform vec3 uGlowColor;
uniform float uGlowIntensity;

void main() {
    vec3 c = uGlowColor * (0.5 + vPulse) * uGlowIntensity;
    FragColor = vec4(c, 0.45);
}
