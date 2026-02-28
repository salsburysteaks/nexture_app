import { useState } from 'react'
import type { Dispatch, SetStateAction } from 'react';
interface SidebarInputsProps {
  setBusinessData: Dispatch<SetStateAction<any | null>>; // matches your useState
}

export default function SidebarInputs({ setBusinessData }: SidebarInputsProps) {
    const [primaryGoal, setPrimaryGoal] = useState("");
    const [salesChannel, setSalesChannel] = useState("");
    const [uniqueness, setUniqueness] = useState<number | "">("");
    const [targetCustomer, setTargetCustomer] = useState("");
    const [productCategory, setProductCategory] = useState("");
    const [leadTime, setLeadTime] = useState<number | "">("");
    const [unitCost, setUnitCost] = useState<number | "">("");
    const [shipPU, setShipPU] = useState<number | "">("");
    const [payFee, setPayFee] = useState<number | "">("");
    const [returns, setReturns] = useState<number | "">("");
    const [monthlyCost, setMonthlyCost] = useState<number | "">("");
    const [demand, setDemand] = useState<number | "">("");
    const [compLow, setCompLow] = useState<number | "">("");
    const [compHigh, setCompHigh] = useState<number | "">("");


    async function sendData() {
      const res = await fetch("http://localhost:3001/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ primaryGoal, salesChannel, 
          targetCustomer, productCategory,
          leadTime, unitCost, shipPU, payFee, returns, monthlyCost, demand, compLow, compHigh })
      });

      const data = await res.json();
      console.log(data.message);
      setBusinessData(data)
  }


    return (
        <div className='flex flex-col gap-4'>
          <h2 className="text-xl font-bold">Inputs</h2>
        <p className="text-sm text-white/70">Enter what you know. Nexture does the math + strategy.</p>

        <div>
          <h2 className='text-xl font-bold pb-4'>Businuess context</h2>
          <label className="block mb-1">Primary goal</label>
          <select className="w-full bg-slate-800 p-2 rounded" onChange={(e) => setPrimaryGoal(e.target.value)}>
            <option>Maximize profit</option>
            <option>Break even fast</option>
            <option>Grow market share</option>
          </select>
        </div>

        <div>
          <label className="block mb-1">Sales channel</label>
          <select className="w-full bg-slate-800 p-2 rounded" onChange={(e) => setSalesChannel(e.target.value)}>
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
          <textarea className='sidebar-textarea' placeholder='e.g. College Students, Busy Parents' onChange={(e) => setTargetCustomer(e.target.value)}></textarea>
        </div>

        <div className='h-10 items-center'>
          <div className='h-[4px] bg-slate-800 w-full'></div>
        </div>

        <h2 className='text-xl font-bold'>Launch Timing</h2>
        <div className=''>
          <p>Product Category</p>
          <select className="w-full bg-slate-800 p-2 rounded" onChange={(e) => setProductCategory(e.target.value)}>
            <option>Gifts / Novelty</option>
            <option>Fashion / Apparel</option>
            <option>Fitness / Wellness</option>
          </select>
        </div>

        <div>
          <label className="block mb-1">Lead time (weeks)</label>
          <input
            type="number"
            className="sidebar-textarea"
            placeholder='0.0'
            onChange={(e) => {
              const value = e.target.value;
              setLeadTime(value === "" ? "" : Number(value));
            }}
          />
        </div>

        <div className='h-10 items-center'>
          <div className='h-[4px] bg-slate-800 w-full'></div>
        </div>

        <h2 className='text-xl font-bold'>Costs & Demand</h2>
        <div>
          <p>Unit Cost / COGS ($)</p>
          <input className='sidebar-textarea' 
          type='number' 
          placeholder='0.0'
          onChange={(e) => {
            const cogVal = e.target.value;
            setUnitCost(cogVal == "" ? "" : Number(cogVal))
          }}></input>
          <p>Shipping/Fullfillment per unit ($)</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'
          onChange={(e) =>{
            const shipPUVal = e.target.value
            setShipPU(shipPUVal == "" ? "" : Number(shipPUVal))
          }}></input>
          <p>Platform/Payment fee (%)</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'
          onChange={(e) => {
            const platformVal = e.target.value
            setPayFee(platformVal == "" ? "": Number(platformVal))
          }}></input>
          <p>Returns/Deduct allowance (%)</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'
          onChange={(e) => {
            const returnVal = e.target.value
            setReturns(returnVal == "" ? "": Number(returnVal))
          }}></input>
          <p>Fixed monthly cost ($)</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'
          onChange={(e) => {
            const costVal = e.target.value
            setMonthlyCost(costVal == "" ? "": Number(costVal))
          }}></input>
          <p>Expected Demand (units/month)</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'
          onChange={(e) => {
            const demandVal = e.target.value
            setDemand(demandVal == "" ? "": Number(demandVal))
          }}></input>
        </div>
        <div>
          <h2 className='text-xl font-bold'>Competitor Pricing</h2>
          <p>Competitor Low</p>
          <input className='sidebar-textarea' 
          type='number' 
          placeholder='0.0'
          onChange={(e) => {
            const compLowVal = e.target.value;
            setCompLow(compLowVal == "" ? "" : Number(compLowVal))
          }}></input>
          <p>Competitor High</p>
          <input className='sidebar-textarea' type='number' placeholder='0.0'
          onChange={(e) =>{
            const compHighVal = e.target.value
            setCompHigh(compHighVal == "" ? "" : Number(compHighVal))
          }}></input>
        </div>
        <button className="w-full bg-indigo-600 hover:bg-indigo-500 p-2 rounded font-semibold" onClick={sendData}>
          Run analysis
        </button>
        </div>
    )
}