import { useState, useEffect } from 'react'
import type { PlatformSummary, AccessMatrix, ProvisioningEvents, AuditLog, DriftResults } from '../types'

// In dev: Vite serves public/data/ (symlink to demo/fixtures/)
// In prod: copyFixtures plugin copies JSON into dist/data/
const BASE = '/data'

async function load<T>(file: string): Promise<T> {
  const res = await fetch(`${BASE}/${file}`)
  if (!res.ok) throw new Error(`Failed to load ${file}: ${res.status}`)
  return res.json()
}

export function usePlatformSummary() {
  const [data, setData] = useState<PlatformSummary | null>(null)
  useEffect(() => { load<PlatformSummary>('platform-summary.json').then(setData) }, [])
  return data
}

export function useAccessMatrix() {
  const [data, setData] = useState<AccessMatrix | null>(null)
  useEffect(() => { load<AccessMatrix>('access-matrix.json').then(setData) }, [])
  return data
}

export function useProvisioningEvents() {
  const [data, setData] = useState<ProvisioningEvents | null>(null)
  useEffect(() => { load<ProvisioningEvents>('provisioning-events.json').then(setData) }, [])
  return data
}

export function useAuditLog() {
  const [data, setData] = useState<AuditLog | null>(null)
  useEffect(() => { load<AuditLog>('audit-log.json').then(setData) }, [])
  return data
}

export function useDriftResults() {
  const [data, setData] = useState<DriftResults | null>(null)
  useEffect(() => { load<DriftResults>('drift-results.json').then(setData) }, [])
  return data
}
