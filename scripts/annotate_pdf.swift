// Render each page of a PDF to a PNG with every AcroForm field widget outlined in
// red and tagged with "#<fieldName>", so an agent can read the printed caption
// next to each box and return {fieldName: label}.
//   swift annotate_pdf.swift <pdf> <outDir> [scale=3.0]
import Foundation
import PDFKit
import AppKit

let args = CommandLine.arguments
guard args.count >= 3 else { FileHandle.standardError.write("usage: annotate_pdf <pdf> <outDir> [scale]\n".data(using: .utf8)!); exit(1) }
let pdfPath = args[1], outDir = args[2]
let scale = CGFloat(args.count > 3 ? (Double(args[3]) ?? 3.0) : 3.0)
guard let doc = PDFDocument(url: URL(fileURLWithPath: pdfPath)) else { FileHandle.standardError.write("cannot open\n".data(using: .utf8)!); exit(1) }
try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

let red = CGColor(red: 0.85, green: 0.05, blue: 0.05, alpha: 1)
for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    let box = page.bounds(for: .mediaBox)
    let w = Int(box.width * scale), h = Int(box.height * scale)
    guard w > 0, h > 0, w < 20000, h < 20000 else { continue }
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
        space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { continue }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.saveGState()
    ctx.scaleBy(x: scale, y: scale)
    ctx.translateBy(x: -box.origin.x, y: -box.origin.y)
    page.draw(with: .mediaBox, to: ctx)
    ctx.restoreGState()

    let nsctx = NSGraphicsContext(cgContext: ctx, flipped: false)
    NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.current = nsctx
    for an in page.annotations where an.fieldName != nil {
        let b = an.bounds
        let r = CGRect(x: (b.origin.x - box.origin.x) * scale, y: (b.origin.y - box.origin.y) * scale,
                       width: b.width * scale, height: b.height * scale)
        ctx.setStrokeColor(red); ctx.setLineWidth(1.3); ctx.stroke(r)
        let label = "#\(an.fieldName!)" as NSString
        let attrs: [NSAttributedString.Key: Any] = [.font: NSFont.boldSystemFont(ofSize: 13), .foregroundColor: NSColor.white]
        let sz = label.size(withAttributes: attrs)
        let ly = min(r.maxY, CGFloat(h) - sz.height)
        ctx.setFillColor(red); ctx.fill(CGRect(x: r.minX, y: ly - sz.height, width: sz.width + 3, height: sz.height + 1))
        label.draw(at: CGPoint(x: r.minX + 1.5, y: ly - sz.height), withAttributes: attrs)
    }
    NSGraphicsContext.restoreGraphicsState()
    guard let img = ctx.makeImage() else { continue }
    let rep = NSBitmapImageRep(cgImage: img)
    if let png = rep.representation(using: .png, properties: [:]) {
        try? png.write(to: URL(fileURLWithPath: "\(outDir)/p\(i).png"))
    }
}
