#version 330 core
in vec2 vUV;
out vec4 FragColor;

uniform sampler2D uInputTex;
uniform vec2 uTexelSize;
uniform float uSmoothStrength;

vec3 rgb2ycbcr(vec3 c) {
    float y  = dot(c, vec3(0.299, 0.587, 0.114));
    float cb = 0.5 + dot(c, vec3(-0.168736, -0.331264, 0.5));
    float cr = 0.5 + dot(c, vec3(0.5, -0.418688, -0.081312));
    return vec3(y, cb, cr);
}

bool isSkin(vec3 rgb) {
    vec3 ycbcr = rgb2ycbcr(rgb);
    // Broad skin range in YCbCr (heuristic).
    return (ycbcr.y > 0.30 && ycbcr.y < 0.62 && ycbcr.z > 0.33 && ycbcr.z < 0.68);
}

void main() {
    vec3 center = texture(uInputTex, vUV).rgb;

    // 9-tap kernel for bilateral-like smoothing.
    vec2 taps[9] = vec2[](
        vec2(-1,-1), vec2(0,-1), vec2(1,-1),
        vec2(-1, 0), vec2(0, 0), vec2(1, 0),
        vec2(-1, 1), vec2(0, 1), vec2(1, 1)
    );
    float w[9] = float[](1,2,1,2,4,2,1,2,1);

    vec3 blur = vec3(0.0);
    float sumW = 0.0;
    for (int i = 0; i < 9; ++i) {
        vec3 s = texture(uInputTex, vUV + taps[i] * uTexelSize).rgb;
        float edge = exp(-20.0 * length(s - center));
        float ww = w[i] * edge;
        blur += s * ww;
        sumW += ww;
    }
    blur /= max(sumW, 1e-5);

    vec3 outColor = center;
    if (isSkin(center)) {
        outColor = mix(center, blur, uSmoothStrength);
    }
    FragColor = vec4(outColor, 1.0);
}
