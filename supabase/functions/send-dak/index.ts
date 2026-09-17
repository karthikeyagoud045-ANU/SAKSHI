import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const supabaseUrl = Deno.env.get('SUPABASE_URL')!
const supabaseServiceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
const waToken = Deno.env.get('WHATSAPP_TOKEN') // For cloud test mode

const supabase = createClient(supabaseUrl, supabaseServiceRoleKey)

interface DakMessage {
  id: string
  ticket_id: string
  payload: {
    blurred_signed_path_placeholder: string
    text_summary: string
    lat: number
    lng: number
    packet_id: string
    order: string[]
  }
  status: string
}

interface ChannelMsg {
  id: string
  msg_id: string
  bubble: any
  ticks: number
  ts: string
}

serve(async (req) => {
  // Only accept POST requests
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 })
  }

  try {
    // Get approved outbox messages
    const { data: messages, error } = await supabase
      .from('outbox_msgs')
      .select('*')
      .eq('status', 'approved')

    if (error) throw error

    // Process each approved message
    for (const msg of messages) {
      // Determine mode: simulator or cloud_test
      const waMode = Deno.env.get('WA_MODE') || 'simulator'
      
      if (waMode === 'cloud_test') {
        // Cloud API branch: stub the actual cloud API call (per R7: no real external sends)
        // In real implementation with WA_MODE='cloud_test', we would attempt to call
        // WhatsApp Cloud API but stub it for safety
        console.log(`[WA_MODE=cloud_test] Stubbing WhatsApp Cloud API call for ticket ${msg.ticket_id}`)
        
        // Still update the outbox message status to simulate successful processing
        const { error: updateError } = await supabase
          .from('outbox_msgs')
          .update({
            status: 'sent',
            sent_at: new Date().toISOString()
          })
          .eq('id', msg.id)

        if (updateError) throw updateError

        // Audit log for cloud test mode
        await supabase.from('audit_log').insert([{
          actor: 'system',
          action: 'dak_sent',
          detail: {
            ticket_id: msg.ticket_id,
            msg_id: msg.id,
            mode: 'cloud_test_stubbed'
          }
        }])
      } else {
        // Simulator mode: write to channel_msgs table (sandbox channel simulator)
        const channelMsg: ChannelMsg = {
          id: crypto.randomUUID(),
          msg_id: msg.id,
          bubble: {
            type: 'dak_message',
            ticket_id: msg.ticket_id,
            payload: msg.payload
          },
          ticks: Date.now(),
          ts: new Date().toISOString()
        }

        // Write to channel_msgs table
        const { error: channelError } = await supabase
          .from('channel_msgs')
          .insert([channelMsg])

        if (channelError) throw channelError

        // Update outbox message status to sent
        const { error: updateError } = await supabase
          .from('outbox_msgs')
          .update({
            status: 'sent',
            sent_at: new Date().toISOString()
          })
          .eq('id', msg.id)

        if (updateError) throw updateError

        // Audit log
        await supabase.from('audit_log').insert([{
          actor: 'system',
          action: 'dak_sent',
          detail: {
            ticket_id: msg.ticket_id,
            msg_id: msg.id,
            mode: 'simulator'
          }
        }])
      }
    }

    return new Response(JSON.stringify({ success: true }), {
      headers: { 'Content-Type': 'application/json' },
      status: 200
    })
  } catch (err) {
    console.error('Error in send-dak function:', err)
    return new Response(JSON.stringify({ error: err.message }), {
      headers: { 'Content-Type': 'application/json' },
      status: 500
    })
  }
})
