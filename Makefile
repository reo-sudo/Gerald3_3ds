# Gerald -- Nintendo 3DS build (devkitARM + libctru + citro2d/citro3d)
#
#   make          builds gerald.3dsx (what GitHub Actions does)
#   make 3dsx     just the Homebrew Launcher version
#   make cia      OPTIONAL installable CIA (needs makerom + bannertool; not part of `make` / CI)
#   make clean
#
# Tools used: arm-none-eabi-gcc, tex3ds, smdhtool, 3dsxtool (all part of devkitPro's 3ds-dev)
#             makerom (CIA), bannertool (HOME-menu banner)

DEVKITPRO ?= /opt/devkitpro
DEVKITARM ?= $(DEVKITPRO)/devkitARM
export PATH := $(CURDIR)/bin:$(DEVKITARM)/bin:$(DEVKITPRO)/tools/bin:$(PATH)

TARGET  := gerald
TITLE   := Gerald
DESC    := A pixel-art virtual pet frog
AUTHOR  := reo

CC      := arm-none-eabi-gcc
ARCH    := -march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft
INCLUDE := -I$(DEVKITPRO)/libctru/include -I$(DEVKITPRO)/portlibs/3ds/include -I$(DEVKITPRO)/portlibs/armv6k/include
CFLAGS  := -g -Wall -O2 -std=gnu11 -mword-relocations -ffunction-sections -fdata-sections $(ARCH) \
           -D__3DS__ -D_GNU_SOURCE=1 $(INCLUDE)
LDFLAGS := -specs=3dsx.specs -g $(ARCH) -Wl,--gc-sections -Wl,-Map,$(TARGET).map
LIBPATHS:= -L$(DEVKITPRO)/libctru/lib -L$(DEVKITPRO)/portlibs/3ds/lib -L$(DEVKITPRO)/portlibs/armv6k/lib
LIBS    := -lcitro2d -lcitro3d -lctru -lm

SRCS    := $(wildcard source/*.c)
OBJS    := $(SRCS:source/%.c=build/%.o)
T3X     := romfs/gfx/sprites.t3x romfs/gfx/bg.t3x romfs/gfx/ui.t3x
SOUNDS  := $(wildcard romfs/snd/*.raw)

.PHONY: all 3dsx cia clean
all: 3dsx
3dsx: $(TARGET).3dsx
cia: $(TARGET).cia

build/%.o: source/%.c
	@mkdir -p build
	$(CC) -MMD -MP $(CFLAGS) -c $< -o $@
-include $(OBJS:.o=.d)

$(TARGET).elf: $(OBJS)
	$(CC) $(LDFLAGS) $(OBJS) $(LIBPATHS) $(LIBS) -o $@

# sprite sheets -> .t3x textures that live in romfs
romfs/gfx/%.t3x: gfx/%.t3s gfx/%.png
	@mkdir -p romfs/gfx
	tex3ds -i $< -o $@

# HOME-menu icon
$(TARGET).smdh: banner/icon.png
	smdhtool --create "$(TITLE)" "$(DESC)" "$(AUTHOR)" $< $@

# Homebrew Launcher build
$(TARGET).3dsx: $(TARGET).elf $(TARGET).smdh $(T3X) $(SOUNDS)
	3dsxtool $< $@ --smdh=$(TARGET).smdh --romfs=romfs

# HOME-menu banner (3D banner image + jingle)
banner.bnr: banner/banner.png banner/banner.wav
	bannertool makebanner -i banner/banner.png -a banner/banner.wav -o $@

# Installable CIA (install with FBI)
$(TARGET).cia: $(TARGET).elf $(TARGET).smdh banner.bnr cia/gerald.rsf $(T3X) $(SOUNDS)
	makerom -f cia -o $@ -elf $(TARGET).elf -rsf cia/gerald.rsf -icon $(TARGET).smdh -banner banner.bnr -exefslogo -target t

clean:
	rm -rf build $(TARGET).elf $(TARGET).3dsx $(TARGET).cia $(TARGET).smdh $(TARGET).map banner.bnr romfs/gfx/*.t3x
