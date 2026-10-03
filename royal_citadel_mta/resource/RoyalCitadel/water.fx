// Screen-space reflections for the moat and fountain basins.
// Inspired by the wet.fx in the user's updated source.zip; tested structurally only.
float4x4 gWorld : WORLD;
float4x4 gWorldViewProjection : WORLDVIEWPROJECTION;
float4x4 gViewProjection : VIEWPROJECTION;
float3 gCameraPosition : CAMERAPOSITION;
float gTime : TIME;
float2 gPix = float2(0.0007, 0.0013);
float gReflect = 0.82;
float3 gTint = float3(0.48, 0.70, 0.82);

texture gTexture0 < string textureState = "0,Texture"; >;
texture gScreen;
texture gNormalMap;

sampler Sampler0 = sampler_state
{
    Texture = (gTexture0);
    MinFilter = Anisotropic;
    MagFilter = Linear;
    MipFilter = Linear;
    MaxAnisotropy = 8;
    AddressU = Wrap;
    AddressV = Wrap;
};
sampler SamplerS = sampler_state
{
    Texture = (gScreen);
    MinFilter = Linear;
    MagFilter = Linear;
    MipFilter = None;
    AddressU = Clamp;
    AddressV = Clamp;
};
sampler SamplerN = sampler_state
{
    Texture = (gNormalMap);
    MinFilter = Linear;
    MagFilter = Linear;
    MipFilter = Linear;
    AddressU = Wrap;
    AddressV = Wrap;
};

struct VSInput
{
    float3 Position : POSITION0;
    float3 Normal : NORMAL0;
    float4 Diffuse : COLOR0;
    float2 TexCoord : TEXCOORD0;
};
struct VSOutput
{
    float4 Position : POSITION0;
    float4 Diffuse : COLOR0;
    float2 TexCoord : TEXCOORD0;
    float3 WorldPos : TEXCOORD1;
    float3 WorldNormal : TEXCOORD2;
};
struct PSInput
{
    float4 Diffuse : COLOR0;
    float2 TexCoord : TEXCOORD0;
    float3 WorldPos : TEXCOORD1;
    float3 WorldNormal : TEXCOORD2;
};
VSOutput VertexShaderFunction(VSInput VS)
{
    VSOutput O = (VSOutput)0;
    O.Position = mul(float4(VS.Position, 1.0), gWorldViewProjection);
    O.WorldPos = mul(float4(VS.Position, 1.0), gWorld).xyz;
    O.WorldNormal = mul(VS.Normal, (float3x3)gWorld);
    O.Diffuse = VS.Diffuse;
    O.TexCoord = VS.TexCoord;
    return O;
}
float4 PixelShaderFunction(PSInput PS) : COLOR0
{
    float4 tex = tex2D(Sampler0, PS.TexCoord);
    float t = gTime;
    float2 uvN = PS.TexCoord * 2.0 + float2(t * 0.018, -t * 0.012);
    float3 nmap = tex2D(SamplerN, uvN).rgb * 2.0 - 1.0;
    float2 ripple = float2(sin((PS.WorldPos.x + t * 0.7) * 1.8), cos((PS.WorldPos.y - t * 0.5) * 1.6)) * 0.025;
    float3 N = normalize(PS.WorldNormal + float3(nmap.x * 0.10 + ripple.x, nmap.y * 0.10 + ripple.y, 0.0));
    float3 V = normalize(PS.WorldPos - gCameraPosition);
    float3 R = reflect(V, N);
    float4 clip = mul(float4(PS.WorldPos + R * 95.0, 1.0), gViewProjection);
    float2 uv = clip.xy / max(clip.w, 0.001) * float2(0.5, -0.5) + 0.5;
    float2 edge = saturate(min(uv, 1.0 - uv) * 9.0);
    float visibility = edge.x * edge.y * step(0.5, clip.w);
    visibility *= saturate(1.0 - length(PS.WorldPos - gCameraPosition) / 230.0);
    float2 offset = gPix * 3.0;
    float3 reflected = tex2D(SamplerS, uv).rgb * 0.40
        + tex2D(SamplerS, uv + float2(offset.x, 0.0)).rgb * 0.15
        + tex2D(SamplerS, uv - float2(offset.x, 0.0)).rgb * 0.15
        + tex2D(SamplerS, uv + float2(0.0, offset.y)).rgb * 0.15
        + tex2D(SamplerS, uv - float2(0.0, offset.y)).rgb * 0.15;
    float fresnel = 0.08 + 0.92 * pow(1.0 - saturate(dot(-V, N)), 5.0);
    float wave = sin((PS.WorldPos.x + PS.WorldPos.y) * 0.24 + t * 1.8) * 0.025;
    float3 base = tex.rgb * gTint + wave;
    float3 colour = lerp(base, reflected, saturate(gReflect * fresnel * visibility));
    return float4(saturate(colour), 1.0);
}
technique tec0
{
    pass P0
    {
        VertexShader = compile vs_3_0 VertexShaderFunction();
        PixelShader = compile ps_3_0 PixelShaderFunction();
    }
}
technique fallback
{
    pass P0 { }
}
