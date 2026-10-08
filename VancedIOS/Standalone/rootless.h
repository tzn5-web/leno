#pragma once
// A sideloaded app has no jailbreak prefix or libroot runtime.
// The upstream fallback path remains unmodified and will simply be absent.
#define ROOT_PATH(path) (path)
#define ROOT_PATH_NS(path) (path)
