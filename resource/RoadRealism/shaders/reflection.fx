//----------------------------------------------------------------
// RoadRealism  -  reflection.fx
// Created by: Arena.ai Agent Mode (AI)
//
// Turns the screen source into the reflection source that road.fx / wetroad.fx sample.
//
//   screen  ->  bright pass (only light sources survive: headlights, street lamps, neon, signs,
//               traffic lights, sky highlights)
//           ->  vertical smear (a wet road stretches a light into a column, it does not mirror it)
//           ->  small horizontal blur
//           ->  reflection render target
//
// Doing this once per frame into a small render target is what keeps the road shader cheap: every
// road pixel then needs exactly ONE reflection tap instead of a blur loop.
// Runs on ps_2_0 (6 texture fetches, no branches).
//----------------------------------------------------------------

texture gSource;      // dxCreateScreenSource
texture gPuddle;      // reused as a low frequency distortion source

sampler sSource = sampler_state { Texture = <gSource>; MinFilter = Linear; MagFilter = Linear; MipFilter = Point; AddressU = Clamp; AddressV = Clamp; };
sampler sPuddle = sampler_state { Texture = <gPuddle>; MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };

float4 gTexel;         // 1/w, 1/h, w, h
float4 gReflParams;    // x = bright threshold, y = smear length, z = distortion, w = strength
float4 gTime;          // x = seconds

struct VSInput
{
    float4 Position : POSITION0;
    float2 TexCoord : TEXCOORD0;
    float4 Diffuse  : COLOR0;
};

struct VSOutput
{
    float4 Position : POSITION0;
    float2 TexCoord : TEXCOORD0;
};

VSOutput ReflVS(VSInput IN)
{
    VSOutput OUT = (VSOutput)0;
    OUT.Position = IN.Position;
    OUT.TexCoord = IN.TexCoord;
    return OUT;
}

float3 Bright(float3 c, float t)
{
    // keep only what is actually a light; a wet road reflects lamps, not the whole world
    float l = dot(c, float3(0.299, 0.587, 0.114));
    return c * saturate((l - t) / max(1.0 - t, 0.05));
}

float4 ReflPS(VSOutput IN) : COLOR0
{
    float2 uv = IN.TexCoord;
    // the aggregate / puddle map breaks the reflection up so it never looks like a mirror
    float2 wob = (tex2D(sPuddle, uv * 3.0 + gTime.x * 0.01).rg - 0.5) * gReflParams.z * gTexel.xy * 6.0;
    uv += wob;

    float3 c = Bright(tex2D(sSource, saturate(uv)).rgb, gReflParams.x);
    // vertical smear: 4 taps down the column, falling off with distance
    float2 step1 = float2(0, gTexel.y) * gReflParams.y;
    c += Bright(tex2D(sSource, saturate(uv + step1 * 1.0)).rgb, gReflParams.x) * 0.72;
    c += Bright(tex2D(sSource, saturate(uv + step1 * 2.0)).rgb, gReflParams.x) * 0.50;
    c += Bright(tex2D(sSource, saturate(uv + step1 * 3.5)).rgb, gReflParams.x) * 0.32;
    c += Bright(tex2D(sSource, saturate(uv + step1 * 5.5)).rgb, gReflParams.x) * 0.20;
    // horizontal blur (2 taps) so the streaks are soft, not pixel columns
    float2 step2 = float2(gTexel.x, 0) * 1.5;
    c += Bright(tex2D(sSource, saturate(uv + step2)).rgb, gReflParams.x) * 0.45;
    c += Bright(tex2D(sSource, saturate(uv - step2)).rgb, gReflParams.x) * 0.45;

    c = c / 3.64 * gReflParams.w;
    return float4(saturate(c), 1.0);
}

technique tec0
{
    pass P0
    {
        VertexShader = compile vs_2_0 ReflVS();
        PixelShader = compile ps_2_0 ReflPS();
    }
}

technique fallback
{
}
