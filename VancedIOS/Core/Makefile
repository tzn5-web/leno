DEBUG = 0
FINALPACKAGE = 1
ARCHS = arm64
TARGET := iphone:clang:latest:14.0

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = VancedIOSCore
VancedIOSCore_FILES = VancedIOSCore.xm
VancedIOSCore_FRAMEWORKS = UIKit Foundation
VancedIOSCore_CFLAGS = -fobjc-arc -Wall -Wextra
include $(THEOS_MAKE_PATH)/tweak.mk
