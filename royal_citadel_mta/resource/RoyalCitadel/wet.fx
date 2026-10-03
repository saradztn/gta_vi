// Created by: Arena.ai Agent Mode (AI) - Royal Citadel MTA:SA resource
// wet.fx - rain response for the Royal Citadel's courtyard paving, controlled by /royalreflect and /royalrain.
//   * wet stone darkens modestly; puddles become darker and smoother
//   * procedural puddles and animated rain rings supplement the generated wetness map
//   * screen-space reflection projects the view ray into the captured frame, softly reflecting walls and lantern coronas
//   * generated marble-roughness data broadens the reflection on rough surfaces
// Shader model 3 (vs_3_0 / ps_3_0).  If the graphics card cannot run it MTA falls back to the empty technique and nothing changes.
float4x4 gWorld : WORLD;
float4x4 gWorldViewProjection : WORLDVIEWPROJECTION;
float4x4 gViewProjection : VIEWPROJECTION;
float3 gCameraPosition : CAMERAPOSITION;
float gTime : TIME;

float gWet = 1.0;                                  // 0 dry .. 1 soaked (script: /ncrain)
float gReflect = 1.0;                              // strength of the mirror term
float2 gPix = float2(0.0007, 0.0013);              // one screen pixel in uv units (script)

texture gTexture0 < string textureState = "0,Texture"; >;
texture gScreen;
texture gWetMask;
texture gRoughnessMap;

sampler Sampler0 = sampler_state
{
    Texture = (gTexture0);
    MinFilter = Anisotropic;
    MagFilter = Linear;
    MipFilter = Linear;
    MaxAnisotropy = 8;
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

sampler SamplerW = sampler_state
{
    Texture = (gWetMask);
    MinFilter = Linear;
    MagFilter = Linear;
    MipFilter = Linear;
    AddressU = Wrap;
    AddressV = Wrap;
};

sampler SamplerR = sampler_state
{
    Texture = (gRoughnessMap);
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

float hash21(float2 p)
{
    return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453);
}

float vnoise(float2 p)
{
    float2 i = floor(p);
    float2 f = frac(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + float2(1.0, 0.0));
    float c = hash21(i + float2(0.0, 1.0));
    float d = hash21(i + float2(1.0, 1.0));
    return lerp(lerp(a, b, f.x), lerp(c, d, f.x), f.y);
}

// slope of the water surface: expanding rings around random drop points on a 1.3 m grid
float2 rainRings(float2 p, float t)
{
    float2 q = p * 0.77;
    float2 g = floor(q);
    float2 f = frac(q) - 0.5;
    float age = frac(t * 0.8 + hash21(g));
    float r = length(f);
    float k = (r - age * 0.45) * 28.0;
    float ring = exp(-k * k) * (1.0 - age);
    return (f / max(r, 0.001)) * ring;
}

float4 PixelShaderFunction(PSInput PS) : COLOR0
{
    float4 tex = tex2D(Sampler0, PS.TexCoord);
    // never darker than a soft floor: the vertex colour can be 0 for some objects once a world shader replaces the stock vertex stage
    float3 vcol = max(PS.Diffuse.rgb, float3(0.20, 0.22, 0.28));
    float3 baseCol = tex.rgb * vcol;

    float3 N = normalize(PS.WorldNormal);
    float up = saturate(N.z);
    float2 wxy = PS.WorldPos.xy;

    // puddles
    float pn = vnoise(wxy * 0.045) * 0.60 + vnoise(wxy * 0.16 + 11.3) * 0.30 + vnoise(wxy * 0.70 + 3.1) * 0.10;
    float proceduralPuddle = smoothstep(0.50, 0.64, pn);
    float paintedPuddle = smoothstep(0.56, 0.84, tex2D(SamplerW, PS.TexCoord * 1.25).r);
    float puddle = max(proceduralPuddle, paintedPuddle * 0.72) * up;

    // wetness: a film everywhere, deeper in the puddles, dry inside the tunnel
    float wet = saturate(gWet * (0.55 + 0.45 * puddle)) * lerp(0.35, 1.0, up);

    baseCol *= lerp(1.0, 0.60, wet);

    // surface normal with rain rings in the puddles
    float2 slope = rainRings(wxy, gTime) * puddle * 0.5;
    float3 Nw = normalize(float3(N.x + slope.x, N.y + slope.y, max(N.z, 0.2)));

    // mirror term
    float3 V = normalize(PS.WorldPos - gCameraPosition);
    float3 R = reflect(V, Nw);
    float3 refPoint = PS.WorldPos + R * 70.0;
    float4 cp = mul(float4(refPoint, 1.0), gViewProjection);
    float2 uv = cp.xy / max(cp.w, 0.001) * float2(0.5, -0.5) + 0.5;
    float2 edge = saturate(min(uv, 1.0 - uv) * 10.0);
    float vis = edge.x * edge.y * step(0.5, cp.w);
    float dist = length(PS.WorldPos - gCameraPosition);
    vis *= saturate(1.0 - dist / 190.0);

    float roughness = tex2D(SamplerR, PS.TexCoord * 1.25).r;
    float blur = lerp(16.0, 5.0, puddle) * lerp(0.75, 1.35, roughness); // pixels: rough film vs. smooth puddle
    float2 o = gPix * blur;
    float3 refl = tex2D(SamplerS, uv).rgb * 0.4
                + tex2D(SamplerS, uv + float2(o.x, 0.0)).rgb * 0.15
                + tex2D(SamplerS, uv - float2(o.x, 0.0)).rgb * 0.15
                + tex2D(SamplerS, uv + float2(0.0, o.y)).rgb * 0.15
                + tex2D(SamplerS, uv - float2(0.0, o.y)).rgb * 0.15;

    float ndv = saturate(dot(-V, Nw));
    float fres = 0.04 + 0.96 * pow(1.0 - ndv, 5.0);
    float strength = wet * (0.22 + 1.25 * fres + 0.55 * puddle) * gReflect * lerp(1.0, 0.72, roughness);
    float3 col = baseCol + refl * strength * vis;
    return float4(saturate(col), 1.0);
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
    pass P0
    {
    }
}
