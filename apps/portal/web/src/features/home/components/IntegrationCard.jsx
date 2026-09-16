import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

const IntegrationCard = ({
  app
}) => {
  const Icon = app?.icon

  const handleConnectClick = () => {
    if (!app?.connectUrl) {
      return
    }

    window.open(app.connectUrl, '_blank', 'noopener,noreferrer')
  }

  return (
    <Card className='w-80 border-none shadow-none'>
      <CardContent className='flex flex-col gap-1'>
        <div className='flex items-start'>
          <div className='flex size-17 shrink-0 items-center justify-center rounded-md border'>
            {Icon ? (
              <Icon className='size-8 text-primary' aria-label={`${app.name} icon`} />
            ) : (
              <span className='size-8 rounded-full bg-muted text-muted-foreground flex items-center justify-center text-sm font-medium'>
                {app?.name?.[0] ?? '?'}
              </span>
            )}
          </div>

          {/* 👉 여기 수정됨: flex-col + items-start */}
          <div className='flex flex-col items-start rounded-md px-2 py-1'>
            <Badge
              className='bg-primary/10 [a&]:hover:bg-primary/5 focus-visible:ring-primary/20 dark:focus-visible:ring-primary/40 text-primary py-1 focus-visible:outline-none'
            >
              {app.name}
            </Badge>
            <p className='text-wrap text-sm ml-2'>{app.description}</p>
          </div>
        </div>

        <div className='flex items-center gap-2.5'>
          <div className='w-full'>
            <Button
              variant='outline'
              size='sm'
              className='w-full rounded-full'
              type='button'
              onClick={handleConnectClick}
              disabled={!app?.connectUrl}
            >
              Connect
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>

  );
}

export default IntegrationCard
