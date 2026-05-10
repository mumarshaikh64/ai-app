#version 330 core
in vec2 vUV;
out vec4 FragColor;

uniform sampler2D uCameraTex;

void main() {
    FragColor = texture(uCameraTex, vUV);
}
