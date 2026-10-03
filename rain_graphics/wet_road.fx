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
    float WorldUp : TEXCOORD1;
    float2 ScreenUV : TEXCOORD2;
};

PSInput VertexShaderFunction(VSInput input)
{
    PSInput output = (PSInput)0;
    output.Position = mul(float4(input.Position, 1.0), gWorldViewProjection);
    output.Diffuse = input.Diffuse;
    output.TexCoord = input.TexCoord;

    float3 worldNormal = normalize(mul(input.Normal, (float3x3)gWorld));
    output.WorldUp = worldNormal.z;

    float inverseW = 1.0 / max(abs(output.Position.w), 0.0001);
    float2 ndc = output.Position.xy * inverseW;
    output.ScreenUV = ndc * float2(0.5, -0.5) + 0.5;
    return output;
}

float4 PixelShaderFunction(PSInput input) : COLOR0
{
    float4 material = tex2D(BaseSampler, input.TexCoord) * input.Diffuse;

    // Keep the pixel program under the Shader Model 2 instruction budget.
    // The generated normal masks vertical walls; no per-pixel normalize/sin/pow.
    float roadMask = saturate((input.WorldUp - 0.48) * 1.9);
    float wet = saturate(uWetness) * roadMask;

    // A cheap moving triangular wave distorts the screen sample like shallow ripples.
    float phase = frac(dot(input.TexCoord, float2(43.0, 19.0)) + uTime * 0.08);
    float ripple = abs(phase * 2.0 - 1.0);
    float2 rippleOffset = (float2(ripple, 1.0 - ripple) - 0.5) * wet * 0.004;
    float2 reflectionUV = saturate(input.ScreenUV + float2(0.0, -0.022) + rippleOffset);
    float3 sceneReflection = tex2D(ScreenSampler, reflectionUV).rgb;

    float3 wetColor = material.rgb * (1.0 - wet * 0.14);
    float reflectionAmount = uScreenValid * wet * uReflectionStrength;
    wetColor = lerp(wetColor, sceneReflection * float3(0.68, 0.77, 0.90), reflectionAmount);

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
