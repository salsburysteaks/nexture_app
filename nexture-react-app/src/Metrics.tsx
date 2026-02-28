import type { Dispatch, SetStateAction } from 'react';

/*
interface BusinessMetrics {
    primaryGoal: string
    salesChannel: string
}*/

interface DataViewerProps {
  businessData: any | null;
}

export default function Metrics({ businessData }: DataViewerProps) {

    return (
        <div>
          <h1 className="text-3xl font-bold pb-4">Current Metrics</h1>
          <div className="grid grid-cols-5 gap-4">
          <div className="bg-white/5 p-4 rounded">
            <p className="text-sm text-white/60">Recommended price</p>
            
            <p className="text-2xl font-bold">$49.00</p>
          </div>
          <div className="bg-white/5 p-4 rounded">
          <p className="text-sm text-white/60">Contribution / Unit</p>
          <p></p>
          </div>
          <div className="bg-white/5 p-4 rounded">
          <p className="text-sm text-white/60">Net margin %</p>
          </div>
          <div className="bg-white/5 p-4 rounded">
          <p className="text-sm text-white/60">Monthly Profit</p>
          </div>
          <div className="bg-white/5 p-4 rounded">
            <p className="text-sm text-white/60">Business Health</p>
          </div>
        </div>
        
        {businessData ? (
        <pre className="whitespace-pre-wrap break-words">
          {JSON.stringify(businessData, null, 2)}
          <p>{businessData.reply.primaryGoal}</p>
        </pre>
      ) : (
        <p></p>
      )}
        </div>
    )
}