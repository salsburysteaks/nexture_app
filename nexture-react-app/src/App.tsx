import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import Chat from './ollama'
import SidebarInputs from './sidebar'
import Metrics from './Metrics'

import './App.css'

function App() {
  const [count, setCount] = useState(0)
  const [businessData, setBusinessData] = useState<any | null>(null);
  return (
    <div className="flex min-h-screen bg-slate-950 text-white">
      
      {/* Sidebar */}
      {/*
      <aside className="w-[400px] bg-slate-900 p-6 space-y-6 text-left items-start">
        <h2 className="text-xl font-bold">Inputs</h2>
        <p className="text-sm text-white/70">Enter what you know. Nexture does the math + strategy.</p>

        <div>
          <h2 className='text-xl font-bold pb-4'>Businuess context</h2>
          <label className="block mb-1">Primary goal</label>
          <select className="w-full bg-slate-800 p-2 rounded">
            <option>Maximize profit</option>
            <option>Break even fast</option>
            <option>Grow market share</option>
          </select>
        </div>

        <div>
          <label className="block mb-1">Sales channel</label>
          <select className="w-full bg-slate-800 p-2 rounded">
            <option>Shopify</option>
            <option>Amazon</option>
            <option>Etsy</option>
          </select>
        </div>
        <div>
          <label className='block mb-1'>How Unique is Your Product</label>

        </div>
        <div>
          <label className='block mb-1'>Target Customer (optional)</label>
          <textarea className='sidebar-textarea' placeholder='e.g. College Students, Busy Parents'></textarea>
        </div>

        <div className='h-10 items-center'>
          <div className='h-[4px] bg-slate-800 w-full'></div>
        </div>

        <h2 className='text-xl font-bold'>Launch Timing</h2>
        <div className=''>
          <p>Product Category</p>
          <select className="w-full bg-slate-800 p-2 rounded">
            <option>Gifts / Novelty</option>
            <option>Fashion / Apparel</option>
            <option>Fitness / Wellness</option>
          </select>
        </div>

        <div>
          <label className="block mb-1">Lead time (weeks)</label>
          <input
            type="number"
            className="w-full bg-slate-800 p-2 rounded"
          />
        </div>

        <div className='h-10 items-center'>
          <div className='h-[4px] bg-slate-800 w-full'></div>
        </div>

        <h2 className='text-xl font-bold'>Costs & Demand</h2>
        <div>
          <p>Unit Cost / COGS ($)</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'></input>
          <p>Shipping/Fullfillment per unit ($)</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'></input>
          <p>Platform/Payment fee (%)</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'></input>
          <p>Returns/Deduct allowance (%)</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'></input>
          <p>Fixed monthly cost ($)</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'></input>
          <p>Expected Demand (units/month)</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'></input>
        </div>
        <button className="w-full bg-indigo-600 hover:bg-indigo-500 p-2 rounded font-semibold">
          Run analysis
        </button>
      </aside>*/}
      <aside className="w-[400px] bg-slate-900 p-6 space-y-6 text-left items-start">
        < SidebarInputs setBusinessData={setBusinessData}/>
      </aside>


      {/* Main Content */}
      <main className="flex-1 p-8 space-y-6">

        {/* Header */}
        <header className="flex items-center gap-8 mb-4">
          <img src='img/Nexture_logo_transparent.png' className='object-contain'></img>
          <div>
            <h1 className="text-3xl font-bold">AI Pricing & Launch Advisor</h1>
            <p className="text-white/70">
              Translate business strategies into plain English
            </p>
          </div>
        </header>

        {/* Tabs */}
        <div className="flex gap-4 border-b border-white/10 pt-8">
          <button className="pb-2 border-b-2 border-indigo-500">
            Advisor
          </button>
          <button className="pb-2 text-white/60">
            History
          </button>
        </div>

        {/* Product Card */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-6">
          <h2 className="text-xl font-semibold mb-4">Product</h2>

          <div className="grid grid-cols-10 gap-4">
            <div className="col-span-3 bg-slate-800 rounded h-40 flex items-center justify-center">
              Image Upload
            </div>

            <textarea
              className="col-span-7 bg-slate-800 p-3 rounded"
              placeholder="Short product description..."
            />
          </div>
        </div>

        {/* Metrics Row */}
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
          <div className="bg-white/5 p-4 rounded">Business Health</div>
        </div>
        </div>


        {/* Verdict Card */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-6">
          <h2 className="text-xl font-semibold mb-2">Operator Verdict</h2>
          <p><b>Verdict:</b> GO</p>
          <p className="text-white/70">
            Unit economics are positive and risk is acceptable.
          </p>
        </div>
        <div>
          {/*< Chat />*/}
        </div>
        <div>
          {/*< SidebarInputs setBusinessData={setBusinessData}/>*/}
          < Metrics businessData={businessData} />
        </div>
      </main>
    </div>
  )
}

export default App
