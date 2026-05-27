import { useState } from "react";
import axios from "axios";

function App() {

  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleFileChange = (e) => {

    const selectedFile = e.target.files[0];

    setFile(selectedFile);

    // IMAGE PREVIEW
    if (selectedFile && selectedFile.type.startsWith("image")) {
      setPreview(URL.createObjectURL(selectedFile));
    } else {
      setPreview(null);
    }
  };

  const handleUpload = async () => {

    if (!file) {
      alert("Please select a file");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {

      setLoading(true);

      const response = await axios.post(
        "http://127.0.0.1:8000/extract",
        formData
      );

      setData(response.data);

    } catch (error) {

      console.log(error);
      alert("Upload failed");

    } finally {

      setLoading(false);
    }
  };

  // DOWNLOAD JSON
  const downloadJSON = () => {

    const blob = new Blob(
      [JSON.stringify(data, null, 2)],
      { type: "application/json" }
    );

    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "receipt_data.json";
    a.click();
  };

  return (

    <div className="min-h-screen bg-gray-100 p-10">

      <div className="max-w-4xl mx-auto bg-white p-8 rounded-2xl shadow-lg">

        <h1 className="text-4xl font-bold mb-6 text-center">
          AI Receipt Extractor
        </h1>

        <div className="flex gap-4 mb-6">

          <input
            type="file"
            className="border p-2 rounded w-full"
            onChange={handleFileChange}
          />

          <button
            onClick={handleUpload}
            className="bg-black text-white px-6 py-2 rounded-lg hover:bg-gray-800"
          >
            Upload
          </button>

        </div>

        {/* IMAGE PREVIEW */}
        {preview && (

          <div className="mb-6">

            <h2 className="text-xl font-semibold mb-3">
              Receipt Preview
            </h2>

            <img
              src={preview}
              alt="receipt preview"
              className="rounded-xl border max-h-96 object-contain"
            />

          </div>

        )}

        {/* LOADING */}
        {loading && (

          <div className="text-center py-10">

            <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-black mx-auto"></div>

            <p className="mt-4 text-lg">
              Processing receipt...
            </p>

          </div>

        )}

        {data && (

          <div className="mt-8">

            <div className="flex justify-end mb-4">

              <button
                onClick={downloadJSON}
                className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700"
              >
                Download JSON
              </button>

            </div>

            <div className="grid grid-cols-2 gap-4 mb-6">

              <div className="bg-gray-100 p-4 rounded-xl">
                <h2 className="font-semibold">Store</h2>
                <p>{data.store}</p>
              </div>

              <div className="bg-gray-100 p-4 rounded-xl">
                <h2 className="font-semibold">Date</h2>
                <p>{data.date}</p>
              </div>

              <div className="bg-gray-100 p-4 rounded-xl">
                <h2 className="font-semibold">Total</h2>
                <p>${data.total}</p>
              </div>

              <div className="bg-gray-100 p-4 rounded-xl">
                <h2 className="font-semibold">Confidence</h2>
                <p>{data.confidence}</p>
              </div>

            </div>

            <h2 className="text-2xl font-bold mb-4">
              Items
            </h2>

            <div className="space-y-3">

              {data.items.map((item, index) => (

                <div
                  key={index}
                  className="flex justify-between bg-gray-50 p-4 rounded-lg border"
                >
                  <span>{item.name}</span>
                  <span>${item.price}</span>
                </div>

              ))}

            </div>

          </div>

        )}

      </div>

    </div>
  );
}

export default App;