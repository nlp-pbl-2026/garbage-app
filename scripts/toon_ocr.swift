// Offline Apple Vision audit of rendered official PDF pages. No network or API.
import Foundation
import Vision
import ImageIO

let arguments = CommandLine.arguments
if arguments.count != 3 { fatalError("usage: toon-ocr input-manifest.json output-directory") }
let manifestURL = URL(fileURLWithPath: arguments[1])
let pages = try JSONSerialization.jsonObject(with: Data(contentsOf: manifestURL)) as! [[String: String]]
let output = URL(fileURLWithPath: arguments[2], isDirectory: true)
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
for page in pages {
    let target = output.appendingPathComponent(page["id"]! + ".json")
    if FileManager.default.fileExists(atPath: target.path),
       let previous = try JSONSerialization.jsonObject(with: Data(contentsOf: target)) as? [String: Any],
       previous["source_sha256"] as? String == page["source_sha256"],
       previous["image_sha256"] as? String == page["image_sha256"] { continue }
    let url = URL(fileURLWithPath: page["image"]!)
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["ja-JP", "en-US"]
    request.usesLanguageCorrection = false
    request.minimumTextHeight = 0.003
    try VNImageRequestHandler(url: url).perform([request])
    let observations: [[String: Any]] = (request.results ?? []).compactMap { observation in
        guard let text = observation.topCandidates(1).first else { return nil }
        let box = observation.boundingBox
        return ["text": text.string, "confidence": text.confidence,
                "box": [box.minX, 1-box.maxY, box.maxX, 1-box.minY]]
    }
    let result: [String: Any] = ["image_sha256": page["image_sha256"]!,
        "source_sha256": page["source_sha256"]!, "engine": "Apple Vision accurate ja-JP/en-US",
        "observations": observations]
    try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
        .write(to: target, options: .atomic)
    print(page["id"]!, observations.count)
    fflush(stdout)
}
