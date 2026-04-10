import { useState, useEffect } from 'react'
import type { PlatformSummary, AccessMatrix, ProvisioningEvents, AuditLog, DriftResults } from '../types'

const BASE = '../../demo/fixtures'

async function load<T>(file: string): Promise<T> {
  const res = await fetch(`${BASE}/${file}`)
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
