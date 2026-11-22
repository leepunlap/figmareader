// OCR a UI screenshot with the macOS Vision framework.
//   swift scripts/ocr.swift <image.png> [--lang zh-Hant] [--min 0.4] [--scale 1]
//
// Prints one line per recognised text block:
//   <x0> <y0> <x1> <y1> <confidence> <text>

import Foundation
import Vision
import AppKit

func die(_ m: String) -> Never {
    FileHandle.standardError.write(("error: " + m + "\n").data(using: .utf8)!)
    exit(2)
}

var args = Array(CommandLine.arguments.dropFirst())
guard !args.isEmpty else { die("usage: ocr.swift <image> [--lang zh-Hant] [--min 0.4]") }

let path = args.removeFirst()
var langs = ["zh-Hant", "zh-Hans", "en-US"]
var minConf: Float = 0.4
var scale: Double = 1.0

var i = 0
while i < args.count {
    switch args[i] {
    case "--lang":
        i += 1; guard i < args.count else { die("--lang needs a value") }
        langs = args[i].split(separator: ",").map(String.init)
    case "--min":
        i += 1; guard i < args.count else { die("--min needs a value") }
        minConf = Float(args[i]) ?? 0.4
    case "--scale":
        i += 1; guard i < args.count else { die("--scale needs a value") }
        scale = Double(args[i]) ?? 1.0
    default:
        die("unknown flag \(args[i])")
    }
    i += 1
}

guard let raw = NSImage(contentsOfFile: path) else { die("cannot open \(path)") }
var rect = NSRect(origin: .zero, size: raw.size)
guard let cg = raw.cgImage(forProposedRect: &rect, context: nil, hints: nil) else {
    die("cannot make CGImage")
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = langs

if scale != 1.0 {
    let w = Int(Double(cg.width) * scale)
    let h = Int(Double(cg.height) * scale)
    if let scaled = CGImageSourceResize(cg, w, h) {
        let handler = VNImageRequestHandler(cgImage: scaled, options: [:])
        try? handler.perform([request])
        let obs = request.results ?? []
        let fx = Double(cg.width) / Double(w)
        let fy = Double(cg.height) / Double(h)
        for o in obs {
            guard let top = o.topCandidates(1).first else { continue }
            if top.confidence < minConf { continue }
            let b = o.boundingBox
            let x0 = Int(b.origin.x * Double(w) * fx)
            let y0 = Int(b.origin.y * Double(h) * fy)
            let x1 = Int((b.origin.x + b.size.width) * Double(w) * fx)
            let y1 = Int((b.origin.y + b.size.height) * Double(h) * fy)
            print("\(x0) \(y0) \(x1) \(y1) \(String(format: "%.2f", top.confidence)) \(top.string)")
        }
        exit(0)
    }
}

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
do {
    try handler.perform([request])
} catch {
    die("perform failed: \(error)")
}

for o in request.results ?? [] {
    guard let top = o.topCandidates(1).first else { continue }
    if top.confidence < minConf { continue }
    let b = o.boundingBox
    // Vision origin is bottom-left; convert to top-left pixel coords.
    let x0 = Int(b.origin.x * Double(cg.width))
    let x1 = Int((b.origin.x + b.size.width) * Double(cg.width))
    let yTop = Int((1.0 - b.origin.y - b.size.height) * Double(cg.height))
    let yBot = Int((1.0 - b.origin.y) * Double(cg.height))
    print("\(x0) \(yTop) \(x1) \(yBot) \(String(format: "%.2f", top.confidence)) \(top.string)")
}

// MARK: - helper

func CGImageSourceResize(_ image: CGImage, _ w: Int, _ h: Int) -> CGImage? {
    let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8,
                        bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)
    guard let ctx else { return nil }
    ctx.interpolationQuality = .high
    ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
    return ctx.makeImage()
}
