ARCHS = arm64
TARGET = iphone:clang:latest:15.0
INSTALL_TARGET_PROCESSES = YouTube
DEBUG = 0
FINALPACKAGE = 1

ifeq ($(PACKAGE_IPA),1)
MODULES = jailed
DISPLAY_NAME = YouTube
BUNDLE_ID = com.google.ios.youtube
VancedCore_IPA = ./tmp/Payload/YouTube.app
REMOVE_EXTENSIONS = 0
CODESIGN_IPA = 0
endif

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = VancedCore
VancedCore_FILES = Sources/VancedCore.m Sources/VancedSettings.m Sources/VancedSponsorBlock.m Sources/VancedRYD.m Sources/VancedShortsUI.m
VancedCore_CFLAGS = -fobjc-arc -Wall -Wextra -Werror -Wno-unused-parameter
VancedCore_FRAMEWORKS = Foundation UIKit

include $(THEOS_MAKE_PATH)/tweak.mk
