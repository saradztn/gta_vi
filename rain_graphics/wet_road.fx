// Lightweight wet-road shader for the original GTA: San Andreas world.
// MTA generates world normals so vertical walls can be masked out.
int CUSTOMFLAGS
<
    string createNormals = "yes";
>;

texture gTexture0;
texture gScreenSource;

float4x4 gWorld;
float4x4 gWorldViewProjection;
float uWetness = 0.0;
float uReflectionStrength = 0.16;
float uScreenValid = 0.0;
float uTime = 0.0;

sampler BaseSampler = sampler_state
{
    Texture = (gTexture0);
    AddressU = Wrap;
    AddressV = Wrap;
    MinFilter = Linear;
    MagFilter = Linear;
    MipFilter = Linear;
};

sampler ScreenSampler = sampler_state
{
    Texture = (gScreenSource);
    AddressU = Clamp;
    AddressV = Clamp;
    MinFilter = Linear;
    MagFilter = Linear;
    MipFilter = Linear;
};

struct VSInput
{
    float3 Position : POSITION0;
    float3 Normal : NORMAL0;
    float4 Diffuse : COLOR0;
    float2 TexCoord : TEXCOORD0;
};

struct PSInput
{
    float4 Position : POSITION0;
    float4 Diffuse : COLOR0;
    float2 TexCoord : TEXCOORD0;
    float3 WorldNormal : TEXCOORD1;
    float2 ScreenUV : TEXCOORD2;
};

PSInput VertexShaderFunction(VSInput input)
{
    PSInput output = (PSInput)0;
    output.Position = mul(float4(input.Position, 1.0), gWorldViewProjection);
    output.Diffuse = input.Diffuse;
    output.TexCoord = input.TexCoord;
    output.WorldNormal = normalize(mul(input.Normal, (float3x3)gWorld));

    float inverseW = 1.0 / max(abs(output.Position.w), 0.0001);
    float2 ndc = output.Position.xy * inverseW;
    output.ScreenUV = ndc * float2(0.5, -0.5) + 0.5;
    return output;
}

float4 PixelShaderFunction(PSInput input) : COLOR0
{
    float4 material = tex2D(BaseSampler, input.TexCoord) * input.Diffuse;
    float wet = saturate(uWetness);

    // Restrict the effect to upward-facing ground/road surfaces.
    float roadMask = saturate((normalize(input.WorldNormal).z - 0.42) * 2.1);
    roadMask = roadMask * roadMask * (3.0 - 2.0 * roadMask);
    wet *= roadMask;

    float ripple = 0.5 + 0.5 * sin(input.TexCoord.x * 43.0 + input.TexCoord.y * 19.0 + uTime * 0.7);
    float2 distortion = float2(
        sin(input.TexCoord.x * 71.0 + uTime),
        cos(input.TexCoord.y * 59.0 - uTime * 0.8)
    ) * (0.0015 + 0.0025 * ripple) * wet;

    // A restrained previous-frame screen sample gives wet asphalt a soft,
    // imperfect reflection. It is intentionally subtle, not a full mirror.
    float2 reflectionUV = saturate(input.ScreenUV + float2(0.0, -0.022) + distortion);
    float3 sceneReflection = tex2D(ScreenSampler, reflectionUV).rgb;

    float3 wetColor = material.rgb * (1.0 - 0.14 * wet);
    float reflectionAmount = uScreenValid * wet * uReflectionStrength * (0.35 + 0.65 * ripple);
    wetColor = lerp(wetColor, sceneReflection * float3(0.68, 0.77, 0.90), reflectionAmount);

    // Moving narrow highlights imitate street-light glints in shallow puddles.
    float glintWave = 0.5 + 0.5 * sin(input.TexCoord.x * 17.0 - input.TexCoord.y * 31.0 + uTime * 0.55);
    float glint = pow(saturate(glintWave), 12.0) * wet * 0.055;
    wetColor += float3(0.78, 0.86, 1.0) * glint;

    return float4(wetColor, material.a);
}

technique WetRoad
{
    pass P0
    {
        VertexShader = compile vs_2_0 VertexShaderFunction();
        PixelShader = compile ps_2_0 PixelShaderFunction();
    }
}

// Safe fallback: if the GPU cannot compile the pixel shader, leave the
// original GTA texture in place and let the native MTA rain still work.
technique fallback
{
    pass P0
    {
        Texture[0] = gTexture0;
    }
}
