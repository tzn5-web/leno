ARCHS = arm64
TARGET = iphone:clang:latest:15.0
INSTALL_TARGET_PROCESSES = YouTube

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = VancedCore
VancedCore_FILES = Sources/VancedCore.m
VancedCore_CFLAGS = -fobjc-arc -Wall -Wextra -Werror -Wno-unused-parameter
VancedCore_FRAMEWORKS = Foundation

include $(THEOS_MAKE_PATH)/tweak.mk
