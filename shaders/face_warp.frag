#version 330 core
in vec2 vUV;
out vec4 FragColor;

uniform sampler2D uInputTex;
uniform vec2 uFaceLandmarks[468]; // NDC landmarks
uniform int uLandmarkCount;
uniform float uEyeScale;
uniform float uFaceSlim;

vec2 ndcToUv(vec2 p) {
    return vec2((p.x + 1.0) * 0.5, (1.0 - p.y) * 0.5);
}

void main() {
    vec2 uv = vUV;

    // FaceMesh indices: left eye center-ish 33, right eye 263, cheek/jaw area approx 234 / 454.
    vec2 leftEye = ndcToUv(uFaceLandmarks[33]);
    vec2 rightEye = ndcToUv(uFaceLandmarks[263]);
    vec2 leftCheek = ndcToUv(uFaceLandmarks[234]);
    vec2 rightCheek = ndcToUv(uFaceLandmarks[454]);

    // Eye enlargement warp: pull UV inward toward eye center.
    float rEye = 0.08;
    vec2 dL = uv - leftEye;
    vec2 dR = uv - rightEye;
    float wL = smoothstep(rEye, 0.0, length(dL));
    float wR = smoothstep(rEye, 0.0, length(dR));
    uv -= dL * wL * uEyeScale;
    uv -= dR * wR * uEyeScale;

    // Face slimming: shift cheeks slightly toward nose center.
    vec2 faceCenter = 0.5 * (leftCheek + rightCheek);
    vec2 dC = uv - faceCenter;
    float cheekW = exp(-pow(abs(dC.y) * 6.0, 2.0));
    uv.x = mix(uv.x, faceCenter.x + dC.x * (1.0 - uFaceSlim), cheekW * 0.4);

    FragColor = texture(uInputTex, uv);
}
