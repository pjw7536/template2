import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

const IntegrationCard = ({
  app
}) => {
  return (
    <Card className='w-80 border-none shadow-none'>
      <CardContent className='flex flex-col gap-2'>
        <div className='flex items-center gap-2.5'>
          <div
            className='flex size-17 shrink-0 items-center justify-center rounded-md border'>
            <img src={app.image} alt={app.name} className='size-9' />
          </div>
          <div className='rounded-md p-2.5'>
            <p className='text-wrap'>{app.description}</p>
          </div>
        </div>
        <div className='flex items-center gap-2.5'>
          <Badge
            className='bg-primary/10 [a&]:hover:bg-primary/5 focus-visible:ring-primary/20 dark:focus-visible:ring-primary/40 text-primary px-3 py-1 focus-visible:outline-none'>
            {app.name}
          </Badge>
          <div className='w-full'>
            <Button variant='outline' size='sm' className='w-full rounded-full'>
              Connect
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default IntegrationCard
