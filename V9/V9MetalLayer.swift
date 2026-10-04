import QuartzCore

final class V9MetalLayer:
    CAMetalLayer
{
    override var drawableSize:
        CGSize
    {
        get {
            super.drawableSize
        }

        set {
            guard newValue.width > 1,
                  newValue.height > 1 else {
                return
            }

            super.drawableSize =
                newValue
        }
    }
}
