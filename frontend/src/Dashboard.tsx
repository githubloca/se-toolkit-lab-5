import { useState, useEffect } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'
import { Bar, Line } from 'react-chartjs-2'
import './Dashboard.css'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
)

const STORAGE_KEY = 'api_key'

interface ScoreBucket {
  bucket: string
  count: number
}

interface TimelineEntry {
  date: string
  submissions: number
}

interface PassRateEntry {
  task: string
  avg_score: number
  attempts: number
}

interface LabOption {
  id: string
  title: string
}

type FetchState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; message: string }

function Dashboard() {
  const [token] = useState(() => localStorage.getItem(STORAGE_KEY) ?? '')
  const [labs, setLabs] = useState<LabOption[]>([])
  const [selectedLab, setSelectedLab] = useState<string>('')

  const [scoresState, setScoresState] = useState<FetchState<ScoreBucket[]>>({
    status: 'idle',
  })
  const [timelineState, setTimelineState] = useState<FetchState<TimelineEntry[]>>({
    status: 'idle',
  })
  const [passRatesState, setPassRatesState] = useState<FetchState<PassRateEntry[]>>({
    status: 'idle',
  })

  useEffect(() => {
    if (!token) return

    fetch('/items/', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((items: unknown[]) => {
        if (Array.isArray(items)) {
          const labItems = items.filter(
            (item): item is { id: number; type: string; title: string } =>
              typeof item === 'object' &&
              item !== null &&
              'type' in item &&
              item.type === 'lab',
          )
          setLabs(
            labItems.map((lab) => ({
              id: `lab-${String(lab.id).padStart(2, '0')}`,
              title: lab.title,
            })),
          )
        }
      })
      .catch((err: Error) => {
        console.error('Failed to fetch labs:', err)
      })
  }, [token])

  useEffect(() => {
    if (!token || !selectedLab) return

    const fetchScores = async () => {
      setScoresState({ status: 'loading' })
      try {
        const res = await fetch(`/analytics/scores?lab=${selectedLab}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data: ScoreBucket[] = await res.json()
        setScoresState({ status: 'success', data })
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Unknown error'
        setScoresState({ status: 'error', message })
      }
    }

    const fetchTimeline = async () => {
      setTimelineState({ status: 'loading' })
      try {
        const res = await fetch(`/analytics/timeline?lab=${selectedLab}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data: TimelineEntry[] = await res.json()
        setTimelineState({ status: 'success', data })
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Unknown error'
        setTimelineState({ status: 'error', message })
      }
    }

    const fetchPassRates = async () => {
      setPassRatesState({ status: 'loading' })
      try {
        const res = await fetch(`/analytics/pass-rates?lab=${selectedLab}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data: PassRateEntry[] = await res.json()
        setPassRatesState({ status: 'success', data })
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Unknown error'
        setPassRatesState({ status: 'error', message })
      }
    }

    fetchScores()
    fetchTimeline()
    fetchPassRates()
  }, [token, selectedLab])

  const scoresChartData = {
    labels: scoresState.status === 'success' ? scoresState.data.map((d) => d.bucket) : [],
    datasets: [
      {
        label: 'Submissions',
        data: scoresState.status === 'success' ? scoresState.data.map((d) => d.count) : [],
        backgroundColor: 'rgba(54, 162, 235, 0.6)',
        borderColor: 'rgba(54, 162, 235, 1)',
        borderWidth: 1,
      },
    ],
  }

  const timelineChartData = {
    labels: timelineState.status === 'success' ? timelineState.data.map((d) => d.date) : [],
    datasets: [
      {
        label: 'Submissions per Day',
        data: timelineState.status === 'success' ? timelineState.data.map((d) => d.submissions) : [],
        borderColor: 'rgba(75, 192, 192, 1)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        tension: 0.1,
      },
    ],
  }

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: false,
      },
    },
  }

  if (!token) {
    return (
      <div className="dashboard-message">
        <p>Please enter your API key in the main app to view the dashboard.</p>
      </div>
    )
  }

  if (labs.length === 0) {
    return (
      <div className="dashboard-message">
        <p>Loading labs...</p>
      </div>
    )
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Analytics Dashboard</h1>
        <div className="lab-selector">
          <label htmlFor="lab-select">Select Lab:</label>
          <select
            id="lab-select"
            value={selectedLab}
            onChange={(e) => setSelectedLab(e.target.value)}
          >
            <option value="">-- Select a lab --</option>
            {labs.map((lab) => (
              <option key={lab.id} value={lab.id}>
                {lab.title}
              </option>
            ))}
          </select>
        </div>
      </header>

      {!selectedLab ? (
        <div className="dashboard-message">
          <p>Please select a lab to view analytics.</p>
        </div>
      ) : (
        <div className="dashboard-content">
          <section className="chart-section">
            <h2>Score Distribution</h2>
            {scoresState.status === 'loading' && <p>Loading...</p>}
            {scoresState.status === 'error' && <p className="error">Error: {scoresState.message}</p>}
            {scoresState.status === 'success' && (
              <Bar data={scoresChartData} options={chartOptions} />
            )}
          </section>

          <section className="chart-section">
            <h2>Submissions Timeline</h2>
            {timelineState.status === 'loading' && <p>Loading...</p>}
            {timelineState.status === 'error' && (
              <p className="error">Error: {timelineState.message}</p>
            )}
            {timelineState.status === 'success' && (
              <Line data={timelineChartData} options={chartOptions} />
            )}
          </section>

          <section className="table-section">
            <h2>Pass Rates per Task</h2>
            {passRatesState.status === 'loading' && <p>Loading...</p>}
            {passRatesState.status === 'error' && (
              <p className="error">Error: {passRatesState.message}</p>
            )}
            {passRatesState.status === 'success' && (
              <table>
                <thead>
                  <tr>
                    <th>Task</th>
                    <th>Avg Score</th>
                    <th>Attempts</th>
                  </tr>
                </thead>
                <tbody>
                  {passRatesState.data.map((entry) => (
                    <tr key={entry.task}>
                      <td>{entry.task}</td>
                      <td>{entry.avg_score.toFixed(1)}</td>
                      <td>{entry.attempts}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>
      )}
    </div>
  )
}

export default Dashboard
