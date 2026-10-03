//----------------------------------------------------------------
// RoadRealism  -  rain.fx
// Created by: Arena.ai Agent Mode (AI)
//
// Full screen rain layer, drawn over the frame with dxDrawImage(shader) on onClientRender.
// It is a LENS effect, not a particle effect - the falling streaks themselves are real 3D
// billboards (rain.lua, dxDrawMaterialLine3D), this pass is what happens on the glass:
//
//   static droplet field  - two scales, refracting the screen through the stored droplet normal
//   running droplets      - the field scrolls downwards, faster as the rain gets heavier
//   mist                  - a short blur that grows with the rain level
//   overcast grade        - slight desaturation / cooling so the whole frame reads as rain
//
// ps_2_0: 5 texture fetches, no branches.
//----------------------------------------------------------------

texture gSource;      // screen source
texture gDrops;       // textures/wet/droplets.png (A = coverage, RG = droplet normal)

sampler sSource = sampler_state { Texture = <gSource>; MinFilter = Linear; MagFilter = Linear; MipFilter = Point; AddressU = Clamp; AddressV = Clamp; };
sampler sDrops  = sampler_state { Texture = <gDrops>;  MinFilter = Linear; MagFilter = Linear; MipFilter = Linear; AddressU = Wrap; AddressV = Wrap; };

float4 gTexel;      // 1/w, 1/h, w, h
float4 gRainFx;     // x = rain 0..1, y = droplet strength, z = mist, w = speed
float4 gTime;       // x = seconds

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

VSOutput RainVS(VSInput IN)
{
    VSOutput OUT = (VSOutput)0;
    OUT.Position = IN.Position;
    OUT.TexCoord = IN.TexCoord;
    return OUT;
}

float4 RainPS(VSOutput IN) : COLOR0
{
    float2 uv = IN.TexCoord;
    float rain = saturate(gRainFx.x);
    float aspect = gTexel.z / max(gTexel.w, 1.0);

    // two droplet layers: big slow drops and a fine fast mist of them
    float2 duv1 = float2(uv.x * aspect, uv.y) * 2.2 + float2(0.11, -gTime.x * 0.055 * gRainFx.w);
    float2 duv2 = float2(uv.x * aspect, uv.y) * 5.1 + float2(0.63, -gTime.x * 0.140 * gRainFx.w);
    float4 d1 = tex2D(sDrops, duv1);
    float4 d2 = tex2D(sDrops, duv2);

    // refract the screen through the droplet lenses (only where a droplet actually is)
    float2 refr = ((d1.rg - 0.5) * d1.a + (d2.rg - 0.5) * d2.a * 0.55) * gRainFx.y * rain;
    float2 suv = saturate(uv + refr * gTexel.xy * 46.0);

    float3 c = tex2D(sSource, suv).rgb;

    // mist: two extra taps, mixed in with the rain level
    float3 blur = tex2D(sSource, saturate(suv + float2(gTexel.x, gTexel.y) * 1.6)).rgb;
    blur += tex2D(sSource, saturate(suv - float2(gTexel.x, gTexel.y) * 1.6)).rgb;
    c = lerp(c, (c + blur) / 3.0, saturate(gRainFx.z * rain));

    // the droplets themselves catch a little light on their top edge
    float glint = saturate(d1.a * (1.0 - d1.g) * 2.0 - 0.35) * rain;
    c += glint * 0.10 * float3(0.9, 0.95, 1.0);

    // overcast grade
    float l = dot(c, float3(0.299, 0.587, 0.114));
    c = lerp(c, l.xxx, 0.10 * rain);
    c *= lerp(1.0, 0.94, rain);
    c = lerp(c, c * float3(0.95, 0.98, 1.04), 0.5 * rain);

    return float4(saturate(c), 1.0);
}

technique tec0
{
    pass P0
    {
        VertexShader = compile vs_2_0 RainVS();
        PixelShader = compile ps_2_0 RainPS();
    }
}

technique fallback
{
}
