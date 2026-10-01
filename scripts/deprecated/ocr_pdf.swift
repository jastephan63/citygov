import Foundation
import PDFKit
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count > 1 else { print("usage: ocr_pdf <pdf> [scale]"); exit(1) }
let url = URL(fileURLWithPath: args[1])
let scale: CGFloat = args.count > 2 ? CGFloat(Double(args[2]) ?? 2.0) : 2.0
guard let doc = PDFDocument(url: url) else { print("OPEN_FAIL"); exit(1) }

for pi in 0..<doc.pageCount {
    guard let page = doc.page(at: pi) else { continue }
    let rect = page.bounds(for: .mediaBox)
    let w = Int(rect.width * scale), h = Int(rect.height * scale)
    guard w>0, h>0,
      let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                          space: CGColorSpaceCreateDeviceRGB(),
                          bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue) else { continue }
    ctx.setFillColor(CGColor(red:1,green:1,blue:1,alpha:1)); ctx.fill(CGRect(x:0,y:0,width:w,height:h))
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    guard let cg = ctx.makeImage() else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["de-DE","de-CH","fr-FR"]
    req.usesLanguageCorrection = true
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    if let obs = req.results as? [VNRecognizedTextObservation] {
        for o in obs {
            guard let t = o.topCandidates(1).first else { continue }
            let b = o.boundingBox   // normalized, origin bottom-left
            // PAGE | minX | minY | width | height | text
            let s = t.string.replacingOccurrences(of: "\t", with: " ")
            print("\(pi)\t\(String(format:"%.4f",b.minX))\t\(String(format:"%.4f",b.minY))\t\(String(format:"%.4f",b.width))\t\(String(format:"%.4f",b.height))\t\(s)")
        }
    }
}
