import CoreGraphics
import CoreText
import Foundation
import ImageIO
import UniformTypeIdentifiers

let defaultOutput = "Leno/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png"
let outputPath = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : defaultOutput

let width = 1024
let height = 1024
let colorSpace = CGColorSpaceCreateDeviceRGB()

guard let context = CGContext(
    data: nil,
    width: width,
    height: height,
    bitsPerComponent: 8,
    bytesPerRow: width * 4,
    space: colorSpace,
    bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue
) else {
    fatalError("Could not create CoreGraphics context")
}

context.setFillColor(CGColor(red: 1.0, green: 0.0, blue: 0.0, alpha: 1.0))
context.fill(CGRect(x: 0, y: 0, width: width, height: height))

let plateRect = CGRect(x: 150, y: 320, width: 724, height: 384)
let platePath = CGPath(
    roundedRect: plateRect,
    cornerWidth: 104,
    cornerHeight: 104,
    transform: nil
)

context.addPath(platePath)
context.setFillColor(CGColor(gray: 1.0, alpha: 1.0))
context.fillPath()

let font = CTFontCreateUIFontForLanguage(.system, 300, nil)
let textColor = CGColor(red: 1.0, green: 0.0, blue: 0.0, alpha: 1.0)

let attributes: [NSAttributedString.Key: Any] = [
    NSAttributedString.Key(kCTFontAttributeName as String): font,
    NSAttributedString.Key(kCTForegroundColorAttributeName as String): textColor
]

let attributed = NSAttributedString(string: "A", attributes: attributes)
let line = CTLineCreateWithAttributedString(attributed)
let bounds = CTLineGetBoundsWithOptions(line, [.useOpticalBounds])

let textX = (CGFloat(width) - bounds.width) / 2.0 - bounds.minX
let textY = (CGFloat(height) - bounds.height) / 2.0 - bounds.minY - 8

context.textPosition = CGPoint(x: textX, y: textY)
CTLineDraw(line, context)

guard let image = context.makeImage() else {
    fatalError("Could not create image")
}

let outputURL = URL(fileURLWithPath: outputPath)
try FileManager.default.createDirectory(
    at: outputURL.deletingLastPathComponent(),
    withIntermediateDirectories: true
)

guard let destination = CGImageDestinationCreateWithURL(
    outputURL as CFURL,
    UTType.png.identifier as CFString,
    1,
    nil
) else {
    fatalError("Could not create PNG destination")
}

CGImageDestinationAddImage(destination, image, nil)

guard CGImageDestinationFinalize(destination) else {
    fatalError("Could not write PNG")
}

print("Generated app icon: \(outputURL.path)")
