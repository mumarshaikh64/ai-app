#version 330 core
in vec2 vUV;
out vec4 FragColor;

uniform sampler2D uOverlayTex;
uniform float uAlpha;

void main() {
    vec4 c = texture(uOverlayTex, vUV);
    FragColor = vec4(c.rgb, c.a * uAlpha);
}
