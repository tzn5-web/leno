# VancedIOS

VancedIOS is the iOS analogue of the Vanced/ReVanced architecture.

It is **not a standalone YouTube clone**. The product is a modular patch layer
that is injected into a user-supplied, decrypted YouTube for iOS application.
The official YouTube UI, account model, Home/Search/Subscriptions/Comments and
Google services remain the host application. VancedIOS adds behavior through
independent tweak modules.

## Architecture

1. **Host** — the user supplies a decrypted YouTube.ipa/YouTube.app.
2. **Patch substrate** — pinned YouMod provides ad filtering, background
   playback, SponsorBlock, player/UI hooks and settings.
3. **PiP integration** — pinned YouPiP enables native Picture in Picture.
4. **Dislike integration** — pinned Return-YouTube-Dislikes.
5. **VancedIOSCore** — our small integration layer registers Vanced-style
   defaults, validates that the required tweak layers are loaded, and carries
   compatibility/diagnostic metadata.
6. **Injector** — cyan/pyzule injects the generated deb/dylib payloads into the
   user-provided IPA. The repository never downloads or redistributes YouTube.
7. **Audit** — verifies dependency pins, build identity and that no proprietary
   YouTube binary is committed to the repository.

## Default behavior

VancedIOSCore registers the following defaults without permanently overriding
user choices:

- background playback enabled;
- SponsorBlock enabled;
- SponsorBlock button/notifications/markers enabled;
- native PiP enabled;
- YouMod owns the ad-blocking hooks (player ads, ad slots, ads coordinator,
  feed ad renderers and promo surfaces);
- original YouTube UI/account/feed/navigation remain intact.

Users can still change settings in YouTube/YouMod after first launch.

## Build products

The normal CI build produces tweak packages only:

- `vancedios-core.deb`
- `youmod.deb`
- `youpip.deb`
- `ryd.deb`

The manual IPA workflow requires the user to provide a direct URL to their own
decrypted YouTube IPA. That file is downloaded only for the job, injected,
validated, packaged as an artifact, then removed by the ephemeral runner.

## Why this replaces the old native client

The previous Swift/MPV client attempted to recreate YouTube. That loses too
many official surfaces and continuously chases YouTube extraction changes.

This architecture patches the actual YouTube iOS application. It therefore
inherits the official Home, Search, subscriptions, channels, comments,
account/login UI and player pipeline, while our modules modify behavior around
them—the closest iOS equivalent to Vanced/ReVanced.
