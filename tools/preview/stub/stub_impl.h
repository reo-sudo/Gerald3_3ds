// Tiny software stand-ins for libctru/citro2d so the REAL game code (source/main.c) can be
// rendered on a PC and dumped to images. Only what main.c uses. Not part of the 3DS build.
#pragma once
#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64;
typedef int16_t s16; typedef int8_t s8; typedef int32_t Result;
#define R_FAILED(r) ((r) < 0)

enum { KEY_A = 1, KEY_B = 2, KEY_SELECT = 4, KEY_START = 8, KEY_DRIGHT = 16, KEY_DLEFT = 32, KEY_L = 64,
       KEY_R = 128, KEY_X = 256, KEY_Y = 512, KEY_DUP = 1024, KEY_DDOWN = 2048, KEY_TOUCH = 1 << 20 };
typedef struct { u16 px, py; } touchPosition;
typedef enum { GFX_TOP, GFX_BOTTOM } gfxScreen_t;
typedef enum { GFX_LEFT, GFX_RIGHT } gfx3dSide_t;

// ---- scripted input / frame hooks (set by the preview harness)
static void (*stub_input_hook)(unsigned frame);
static void (*stub_frame_hook)(unsigned frame);
static unsigned stub_frame, stub_max_frames = 10;
static u32 stub_kdown, stub_kheld;
static touchPosition stub_touch;

static void gfxInitDefault(void) {}
static void gfxExit(void) {}
static void gfxFlushBuffers(void) {}
static void gfxSwapBuffers(void) {}
static void gspWaitForVBlank(void) {}
static void consoleInit(gfxScreen_t s, void *p) { (void)s; (void)p; }
static Result romfsInit(void) { return 0; }
static Result romfsExit(void) { return 0; }
static bool aptMainLoop(void) { return stub_frame < stub_max_frames; }
static void hidScanInput(void) {
    stub_kdown = stub_kheld = 0;
    if (stub_input_hook) stub_input_hook(stub_frame);
}
static u32 hidKeysDown(void) { return stub_kdown; }
static u32 hidKeysHeld(void) { return stub_kheld; }
static void hidTouchRead(touchPosition *t) { *t = stub_touch; }
static void *linearAlloc(size_t n) { return malloc(n); }
static void linearFree(void *p) { free(p); }
static Result DSP_FlushDataCache(const void *a, u32 n) { (void)a; (void)n; return 0; }

// audio: pretend there is no DSP firmware
enum { NDSP_OUTPUT_STEREO = 1, NDSP_INTERP_LINEAR = 1, NDSP_FORMAT_MONO_PCM16 = 1 };
typedef struct tag_ndspWaveBuf { union { s16 *data_pcm16; const void *data_vaddr; }; u32 nsamples; void *adpcm_data; u32 offset; bool looping; u8 status; u16 sequence_id; struct tag_ndspWaveBuf *next; } ndspWaveBuf;
static Result ndspInit(void) { return -1; }
static void ndspExit(void) {}
static void ndspSetOutputMode(int m) { (void)m; }
static void ndspSetMasterVol(float v) { (void)v; }
static void ndspChnReset(int c) { (void)c; }
static void ndspChnSetInterp(int c, int i) { (void)c; (void)i; }
static void ndspChnSetRate(int c, float r) { (void)c; (void)r; }
static void ndspChnSetFormat(int c, u16 f) { (void)c; (void)f; }
static void ndspChnSetMix(int c, float *m) { (void)c; (void)m; }
static void ndspChnWaveBufAdd(int c, ndspWaveBuf *b) { (void)c; (void)b; }
static void ndspChnSetPaused(int c, bool p) { (void)c; (void)p; }

// ---- graphics
#define C3D_DEFAULT_CMDBUF_SIZE 0
#define C2D_DEFAULT_MAX_OBJECTS 4096
#define C3D_FRAME_SYNCDRAW 2
enum { GPU_NEAREST = 0 };
#define C2D_Color32(r, g, b, a) ((u32)(r) | ((u32)(g) << 8) | ((u32)(b) << 16) | ((u32)(a) << 24))

typedef struct { int w, h; u8 *px; } C3D_Tex;                       // RGBA
typedef struct C3D_RenderTarget_ { int w, h; u8 *px; } C3D_RenderTarget;
typedef struct { u16 width, height; float left, top, right, bottom; } Tex3DS_SubTexture;
typedef struct { C3D_Tex *tex; const Tex3DS_SubTexture *subtex; } C2D_Image;
typedef struct { u32 color; float blend, alpha; } C2D_ImageTint;
typedef struct { C3D_Tex tex; Tex3DS_SubTexture sub; } StubSheet;
typedef StubSheet *C2D_SpriteSheet;

static C3D_RenderTarget stubTop = {400, 240, NULL}, stubBot = {320, 240, NULL}, *stubCur;

static int C3D_Init(size_t n) { (void)n; return 1; }
static void C3D_Fini(void) {}
static bool C2D_Init(size_t n) { (void)n; return true; }
static void C2D_Prepare(void) {}
static void C2D_Fini(void) {}
static C3D_RenderTarget *C2D_CreateScreenTarget(gfxScreen_t s, gfx3dSide_t d) {
    (void)d;
    C3D_RenderTarget *t = s == GFX_TOP ? &stubTop : &stubBot;
    if (!t->px) t->px = calloc((size_t)t->w * t->h, 4);
    return t;
}
static bool C3D_FrameBegin(u8 f) { (void)f; return true; }
static void C3D_FrameEnd(u8 f) { (void)f; if (stub_frame_hook) stub_frame_hook(stub_frame); stub_frame++; }
static void C3D_TexSetFilter(C3D_Tex *t, int a, int b) { (void)t; (void)a; (void)b; }

static void C2D_TargetClear(C3D_RenderTarget *t, u32 c) {
    for (int i = 0; i < t->w * t->h; i++) memcpy(t->px + i * 4, &c, 4);
}
static void C2D_SceneBegin(C3D_RenderTarget *t) { stubCur = t; }

static C2D_SpriteSheet C2D_SpriteSheetLoad(const char *path) {
    const char *base = strrchr(path, '/');
    base = base ? base + 1 : path;
    char name[64], file[256];
    snprintf(name, sizeof name, "%s", base);
    char *dot = strrchr(name, '.');
    if (dot) *dot = 0;
    const char *dir = getenv("PREVIEW_DIR");
    snprintf(file, sizeof file, "%s/%s.rgba", dir ? dir : ".", name);
    FILE *f = fopen(file, "rb");
    if (!f) { fprintf(stderr, "stub: missing %s\n", file); return NULL; }
    uint32_t wh[2];
    if (fread(wh, 4, 2, f) != 2) { fclose(f); return NULL; }
    StubSheet *s = calloc(1, sizeof *s);
    s->tex.w = (int)wh[0];
    s->tex.h = (int)wh[1];
    s->tex.px = malloc((size_t)wh[0] * wh[1] * 4);
    if (fread(s->tex.px, 4, (size_t)wh[0] * wh[1], f) != (size_t)wh[0] * wh[1]) { fclose(f); return NULL; }
    fclose(f);
    s->sub = (Tex3DS_SubTexture){(u16)wh[0], (u16)wh[1], 0, 1, 1, 0};
    return s;
}
static void C2D_SpriteSheetFree(C2D_SpriteSheet s) { (void)s; }
static C2D_Image C2D_SpriteSheetGetImage(C2D_SpriteSheet s, size_t i) { (void)i; return (C2D_Image){&s->tex, &s->sub}; }
static void C2D_PlainImageTint(C2D_ImageTint *t, u32 c, float b) { t->color = c; t->blend = b; t->alpha = 1; }
static void C2D_AlphaImageTint(C2D_ImageTint *t, float a) { t->color = 0; t->blend = 0; t->alpha = a; }

static void stub_blend(int x, int y, int r, int g, int b, float a) {
    C3D_RenderTarget *t = stubCur;
    if (x < 0 || y < 0 || x >= t->w || y >= t->h || a <= 0) return;
    u8 *p = t->px + ((size_t)y * t->w + x) * 4;
    p[0] = (u8)(r * a + p[0] * (1 - a));
    p[1] = (u8)(g * a + p[1] * (1 - a));
    p[2] = (u8)(b * a + p[2] * (1 - a));
    p[3] = 255;
}
static bool C2D_DrawImageAt(C2D_Image img, float x, float y, float z, const C2D_ImageTint *tint, float sx, float sy) {
    (void)z;
    const C3D_Tex *tx = img.tex;
    const Tex3DS_SubTexture *st = img.subtex;
    int u0 = (int)lroundf(st->left * tx->w), v0 = (int)lroundf((1.0f - st->top) * tx->h);
    int dw = (int)(st->width * sx), dh = (int)(st->height * sy);
    for (int dy = 0; dy < dh; dy++)
        for (int dx = 0; dx < dw; dx++) {
            int u = u0 + (int)(dx / sx), v = v0 + (int)(dy / sy);
            const u8 *p = tx->px + ((size_t)v * tx->w + u) * 4;
            float a = p[3] / 255.0f * (tint ? tint->alpha : 1);
            int r = p[0], g = p[1], b = p[2];
            if (tint && tint->blend > 0) { r = tint->color & 255; g = (tint->color >> 8) & 255; b = (tint->color >> 16) & 255; }
            stub_blend((int)x + dx, (int)y + dy, r, g, b, a);
        }
    return true;
}
static bool C2D_DrawRectSolid(float x, float y, float z, float w, float h, u32 c) {
    (void)z;
    for (int j = 0; j < (int)h; j++)
        for (int i = 0; i < (int)w; i++)
            stub_blend((int)x + i, (int)y + j, c & 255, (c >> 8) & 255, (c >> 16) & 255, ((c >> 24) & 255) / 255.0f);
    return true;
}
static bool C2D_DrawLine(float x0, float y0, u32 c0, float x1, float y1, u32 c1, float th, float z) {
    (void)c1; (void)z;
    int n = (int)fmaxf(fabsf(x1 - x0), fabsf(y1 - y0)) + 1;
    for (int i = 0; i <= n; i++) {
        float t = (float)i / n;
        C2D_DrawRectSolid(x0 + (x1 - x0) * t - th / 2, y0 + (y1 - y0) * t - th / 2, 0, th, th, c0);
    }
    return true;
}
