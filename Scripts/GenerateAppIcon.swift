import AppKit
import Foundation

let defaultOutput = "Leno/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png"
let outputPath = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : defaultOutput

let size = 1024

guard let bitmap = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: size,
    pixelsHigh: size,
    bitsPerSample: 8,
    samplesPerPixel: 3,
    hasAlpha: false,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
) else {
    fatalError("Could not create bitmap")
}

guard let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
    fatalError("Could not create graphics context")
}

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context

let canvas = NSRect(x: 0, y: 0, width: size, height: size)
NSColor(calibratedRed: 1.0, green: 0.0, blue: 0.0, alpha: 1.0).setFill()
canvas.fill()

let plate = NSRect(x: 150, y: 320, width: 724, height: 384)
let platePath = NSBezierPath(roundedRect: plate, xRadius: 104, yRadius: 104)
NSColor.white.setFill()
platePath.fill()

let paragraph = NSMutableParagraphStyle()
paragraph.alignment = .center

let attributes: [NSAttributedString.Key: Any] = [
    .font: NSFont.systemFont(ofSize: 300, weight: .black),
    .foregroundColor: NSColor(calibratedRed: 1.0, green: 0.0, blue: 0.0, alpha: 1.0),
    .paragraphStyle: paragraph
]

("A" as NSString).draw(
    in: NSRect(x: 150, y: 342, width: 724, height: 330),
    withAttributes: attributes
)

NSGraphicsContext.restoreGraphicsState()

guard let data = bitmap.representation(using: .png, properties: [:]) else {
    fatalError("Could not encode PNG")
}

let outputURL = URL(fileURLWithPath: outputPath)
try FileManager.default.createDirectory(
    at: outputURL.deletingLastPathComponent(),
    withIntermediateDirectories: true
)
try data.write(to: outputURL, options: .atomic)

print("Generated app icon: \(outputURL.path)")
