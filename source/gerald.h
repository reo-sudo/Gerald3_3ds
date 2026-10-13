// Gerald -- pet simulation. Pure C, no 3DS dependencies, so it can be unit-tested on a PC.
#pragma once
#include <stdbool.h>
#include <stdint.h>

// life stages (same order as the sprite rows)
enum { G_EGG = 0, G_TADPOLE, G_FROGLET, G_FROG, G_ELDER };

// events reported by the simulation (bit flags)
enum {
    EV_HATCHED = 1 << 0,
    EV_EVOLVED = 1 << 1,
    EV_POOPED  = 1 << 2,
    EV_SICK    = 1 << 3,
    EV_FAINTED = 1 << 4,
    EV_HUNGRY  = 1 << 5,
    EV_SLEEPY  = 1 << 6,
    EV_WOKE    = 1 << 7,
    EV_DIRTY   = 1 << 8,
    EV_SAD     = 1 << 9,
};

// results of player actions
typedef enum {
    ACT_OK = 0,
    ACT_EGG,            // still an egg
    ACT_FAINTED,        // needs medicine first
    ACT_SLEEPING,       // lights are off
    ACT_FULL,           // not hungry
    ACT_NOT_SICK,
    ACT_REVIVED,        // medicine woke him up
    ACT_NOT_TIRED,      // not sleepy yet
    ACT_TOO_TIRED,      // too tired to play
    ACT_TOO_SICK,       // too sick to play
    ACT_ALREADY_CLEAN,
    ACT_TUMMY_ACHE,     // too many snacks...
} ActResult;

typedef enum { M_IDLE, M_HAPPY, M_SAD, M_SICK, M_SLEEP, M_FAINT } Mood;
typedef enum { NEED_NONE, NEED_FAINT, NEED_SICK, NEED_SLEEP, NEED_FOOD, NEED_POOP, NEED_JOY } Need;

#define G_MAGIC 0x444C5247u /* 'GRLD' */
#define G_VERSION 1u
#define G_MAX_POOPS 4

typedef struct {
    uint32_t magic;
    uint32_t version;

    uint8_t stage;
    uint8_t sleeping;
    uint8_t sick;
    uint8_t fainted;
    uint8_t poops;
    uint8_t flags;      // edge-detection for "needs" notifications
    uint8_t pad[2];

    float food, joy, clean, energy, health;   // 0..100
    float poop_timer;                          // seconds until next poop, <0 = none pending
    float snack_load;                          // recent snacks (decays)
    double age;                                // seconds since hatching
    double egg_time;                           // seconds spent as an egg

    uint32_t meals, snacks, flies_caught, games_played, best_score;
    uint32_t rng;
    int64_t last_time;                         // unix time of last update (for offline catch-up)

    uint32_t checksum;
} Gerald;

// --- lifecycle -------------------------------------------------------------
void g_new(Gerald *g, int64_t now);
bool g_save(const Gerald *g, const char *path);
bool g_load(Gerald *g, const char *path);

// --- simulation ------------------------------------------------------------
// advance by dt seconds of real time. scale<1 slows the stat decay (used offline).
uint32_t g_step(Gerald *g, double dt, double scale);
// apply time that passed while the game was closed (capped + slowed). returns events.
uint32_t g_catchup(Gerald *g, int64_t now);
// debug: pretend `seconds` of normal time passed
uint32_t g_skip(Gerald *g, double seconds);

// --- queries ---------------------------------------------------------------
Mood g_mood(const Gerald *g);
Need g_need(const Gerald *g);
const char *g_stage_name(int stage);

// --- actions ---------------------------------------------------------------
ActResult g_feed_meal(Gerald *g);
ActResult g_feed_snack(Gerald *g);
ActResult g_clean(Gerald *g);
ActResult g_toggle_lights(Gerald *g);
ActResult g_medicine(Gerald *g);
ActResult g_can_play(const Gerald *g);
void g_finish_game(Gerald *g, int score);
void g_pet(Gerald *g);
