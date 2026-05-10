#version 330 core
in vec2 vUV;
out vec4 FragColor;

uniform sampler2D uSceneTex;
uniform sampler2D uCameraTex;
uniform sampler2D uBgTex;
uniform sampler2D uMaskTex;
uniform sampler2D uTrailTex[5];

uniform float uHueShift;
uniform float uSaturation;
uniform float uBrightness;
uniform float uContrast;
uniform float uVignette;

vec3 hueRotate(vec3 c, float a) {
    const vec3 k = vec3(0.57735);
    float cosA = cos(a);
    return c * cosA + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - cosA);
}

void main() {
    float m = texture(uMaskTex, vUV).r;
    vec3 cam = texture(uCameraTex, vUV).rgb;
    vec3 bg = texture(uBgTex, vUV).rgb;

    // Background replacement via segmentation mask.
    vec3 base = (m < 0.5) ? bg : cam;

    // Overlay scene render with light blend.
    vec3 scene = texture(uSceneTex, vUV).rgb;
    vec3 outC = mix(base, scene, 0.75);

    // Motion trail / ghost blend from history textures.
    float alpha[5] = float[](0.25, 0.18, 0.13, 0.09, 0.06);
    for (int i = 0; i < 5; ++i) {
        outC += texture(uTrailTex[i], vUV).rgb * alpha[i];
    }

    // Color grade controls.
    outC = hueRotate(outC, uHueShift);
    float luma = dot(outC, vec3(0.299, 0.587, 0.114));
    outC = mix(vec3(luma), outC, uSaturation);
    outC = (outC - 0.5) * uContrast + 0.5 + uBrightness;

    // Vignette.
    float d = distance(vUV, vec2(0.5));
    float vig = smoothstep(0.8, 0.2, d);
    outC *= mix(1.0 - uVignette, 1.0, vig);

    FragColor = vec4(clamp(outC, 0.0, 1.0), 1.0);
}
