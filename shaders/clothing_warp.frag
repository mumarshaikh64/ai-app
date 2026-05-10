#version 330 core
in vec2 vUV;
out vec4 FragColor;

uniform sampler2D uClothTex;
uniform float uAlpha;

void main() {
    vec4 c = texture(uClothTex, vUV);
    FragColor = vec4(c.rgb, uAlpha);
}
